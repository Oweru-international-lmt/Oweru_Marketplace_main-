from collections.abc import Mapping

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Case, Exists, IntegerField, OuterRef, Value, When
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.audit.services import create_audit_log
from apps.lister_identity.evidence import normalize_evidence_reference
from apps.lister_identity.models import ListerIdentity
from apps.lister_identity.services import add_calendar_months
from apps.local_officials.policies import can_review_field_verification
from apps.properties.models import PropertyRecord
from apps.properties.policies import can_update_property_record, get_active_persisted_actor
from apps.roles.catalog import ROLE_VERIFIER
from apps.roles.services import user_has_role

from .audit_events import (
    VERIFICATION_DOCUMENT_APPROVED,
    VERIFICATION_DOCUMENT_EXPIRED,
    VERIFICATION_DOCUMENT_REJECTED,
    VERIFICATION_DOCUMENT_REVOKED,
    VERIFICATION_DOCUMENT_SUBMITTED,
    VERIFICATION_FIELD_APPROVED,
    VERIFICATION_FIELD_EXPIRED,
    VERIFICATION_FIELD_REJECTED,
    VERIFICATION_FIELD_REVOKED,
    VERIFICATION_FIELD_SUBMITTED,
    VERIFICATION_PROPERTY_CHANGE_INVALIDATED,
)
from .models import PropertyVerification, PropertyVerificationEvidence


PROPERTY_VERIFICATION_MATERIAL_FIELDS = frozenset({
    "category",
    "pin",
    "boundary",
    "region",
    "district",
    "ward",
    "locality",
    "stated_size",
    "size_unit",
    "title_type",
})


def _current_time(at=None):
    return at or timezone.now()


def _active_persisted_actor(actor):
    persisted = get_active_persisted_actor(actor)
    if persisted is None:
        raise PermissionDenied("An active persisted account is required.")
    return persisted


def _document_verification_for_update(verification):
    verification_id = verification.pk if isinstance(verification, PropertyVerification) else verification
    try:
        document = (
            PropertyVerification.objects.select_for_update(of=("self",))
            .select_related("property", "submitted_by", "reviewed_by")
            .get(pk=verification_id)
        )
    except PropertyVerification.DoesNotExist as exc:
        raise NotFound("Property verification was not found.") from exc
    if document.kind != PropertyVerification.Kind.DOCUMENT:
        raise ValidationError("This service supports document verification only.")
    return document


def _field_verification_for_update(verification):
    verification_id = verification.pk if isinstance(verification, PropertyVerification) else verification
    try:
        field = (
            PropertyVerification.objects.select_for_update(of=("self",))
            .select_related("property", "submitted_by", "reviewed_by")
            .get(pk=verification_id)
        )
    except PropertyVerification.DoesNotExist as exc:
        raise NotFound("Property verification was not found.") from exc
    if field.kind != PropertyVerification.Kind.FIELD:
        raise ValidationError("This service supports field verification only.")
    return field


def _property_for_submission(property_record):
    property_id = property_record.pk if isinstance(property_record, PropertyRecord) else property_record
    try:
        return PropertyRecord.objects.select_for_update().get(pk=property_id)
    except PropertyRecord.DoesNotExist as exc:
        raise NotFound("Property record was not found.") from exc


def _require_document_submitter(actor, property_record):
    actor = _active_persisted_actor(actor)
    if not can_update_property_record(actor, property_record):
        raise PermissionDenied("You do not have access to submit verification for this property.")
    if not has_effective_lister_identity(user=actor):
        raise ValidationError("An effective Level 1 identity is required.")
    return actor


def _require_document_verifier(actor):
    actor = _active_persisted_actor(actor)
    if not user_has_role(actor, ROLE_VERIFIER):
        raise PermissionDenied("An active Verifier role is required.")
    return actor


def _require_field_submitter(actor, property_record):
    actor = _active_persisted_actor(actor)
    if not can_update_property_record(actor, property_record):
        raise PermissionDenied("You do not have access to submit verification for this property.")
    if get_effective_verification_level(user=actor, property_record=property_record) < 2:
        raise ValidationError("An effective Level 2 property verification is required.")
    return actor


def _require_field_reviewer(actor, field):
    actor = _active_persisted_actor(actor)
    if not can_review_field_verification(actor, field):
        raise PermissionDenied("You do not have access to review this field verification.")
    return actor


def _subject_snapshot(property_record):
    return {
        "property_id": property_record.property_id,
        "category": property_record.category,
        "title_type": property_record.title_type,
        "stated_size": str(property_record.stated_size),
        "size_unit": property_record.size_unit,
        "region_id": str(property_record.region_id),
        "district_id": str(property_record.district_id),
        "ward_id": str(property_record.ward_id),
        "locality_id": str(property_record.locality_id),
    }


def _normalize_document_evidence(evidence):
    if not isinstance(evidence, (list, tuple)) or not evidence:
        raise ValidationError({"evidence": "At least one title document evidence item is required."})

    normalized = []
    for item in evidence:
        if not isinstance(item, Mapping):
            raise ValidationError({"evidence": "Evidence items must be objects."})
        if set(item) != {"evidence_type", "evidence_ref"}:
            raise ValidationError({"evidence": "Evidence items must contain evidence_type and evidence_ref only."})
        if item["evidence_type"] != PropertyVerificationEvidence.EvidenceType.TITLE_DOCUMENT:
            raise ValidationError({"evidence_type": "Document verification requires title document evidence."})
        normalized.append({
            "evidence_type": PropertyVerificationEvidence.EvidenceType.TITLE_DOCUMENT,
            "evidence_ref": normalize_evidence_reference(item["evidence_ref"], field_name="evidence_ref"),
        })
    return normalized


def _normalize_field_evidence(evidence):
    if not isinstance(evidence, (list, tuple)) or not evidence:
        raise ValidationError({"evidence": "At least one field or official evidence item is required."})

    permitted_types = {
        PropertyVerificationEvidence.EvidenceType.FIELD_REPORT,
        PropertyVerificationEvidence.EvidenceType.OFFICIAL_ATTESTATION,
    }
    normalized = []
    for item in evidence:
        if not isinstance(item, Mapping):
            raise ValidationError({"evidence": "Evidence items must be objects."})
        if set(item) != {"evidence_type", "evidence_ref"}:
            raise ValidationError({"evidence": "Evidence items must contain evidence_type and evidence_ref only."})
        if item["evidence_type"] not in permitted_types:
            raise ValidationError({"evidence_type": "Field verification requires field or official evidence."})
        normalized.append({
            "evidence_type": item["evidence_type"],
            "evidence_ref": normalize_evidence_reference(item["evidence_ref"], field_name="evidence_ref"),
        })
    return normalized


def _normalize_rejection_reason(reason):
    if not isinstance(reason, str):
        raise ValidationError({"reason": "A rejection reason is required."})
    normalized = " ".join(reason.split())
    if not normalized:
        raise ValidationError({"reason": "A rejection reason is required."})
    if len(normalized) > 1000:
        raise ValidationError({"reason": "Rejection reason is too long."})
    return normalized


def _audit_state(verification):
    return {
        "property_id": verification.property.property_id,
        "verification_id": str(verification.pk),
        "kind": verification.kind,
        "status": verification.status,
    }


def _audit_transition(*, action, actor, verification, before, request=None):
    create_audit_log(
        actor=actor,
        action=action,
        entity_type="PropertyVerification",
        entity_id=verification.pk,
        before=before,
        after=_audit_state(verification),
        request=request,
    )


@transaction.atomic
def invalidate_property_verifications_for_material_change(*, property_record, changed_fields, actor, request=None):
    material_changes = sorted(set(changed_fields) & PROPERTY_VERIFICATION_MATERIAL_FIELDS)
    if not material_changes:
        return []

    affected = list(
        PropertyVerification.objects.select_for_update(of=("self",))
        .select_related("property")
        .filter(
            property=property_record,
            status__in=[PropertyVerification.Status.PENDING, PropertyVerification.Status.APPROVED],
        )
        .order_by("kind", "submitted_at", "id")
    )
    for verification in affected:
        before = _audit_state(verification)
        verification.status = PropertyVerification.Status.REVOKED
        verification.revoked_at = timezone.now()
        verification.save(update_fields=["status", "revoked_at", "updated_at"])
        after = _audit_state(verification)
        after["changed_fields"] = material_changes
        create_audit_log(
            actor=actor,
            action=VERIFICATION_PROPERTY_CHANGE_INVALIDATED,
            entity_type="PropertyVerification",
            entity_id=verification.pk,
            before=before,
            after=after,
            request=request,
        )
    return affected


def calculate_document_verification_expires_at(approved_at):
    return add_calendar_months(approved_at, settings.PROPERTY_DOCUMENT_VERIFICATION_VALIDITY_MONTHS)


def calculate_field_verification_expires_at(approved_at):
    return add_calendar_months(approved_at, settings.PROPERTY_FIELD_VERIFICATION_VALIDITY_MONTHS)


def has_effective_lister_identity(*, user, at=None):
    user_id = getattr(user, "pk", None)
    if not user_id:
        return False
    return ListerIdentity.objects.filter(
        user_id=user_id,
        status=ListerIdentity.Status.APPROVED,
        expires_at__isnull=False,
        expires_at__gt=_current_time(at),
    ).exists()


def get_effective_property_verifications(*, kind, at=None):
    return PropertyVerification.objects.filter(
        kind=kind,
        status=PropertyVerification.Status.APPROVED,
        expires_at__isnull=False,
        expires_at__gt=_current_time(at),
    )


def filter_queryset_with_effective_property_verification(queryset, *, kind, at=None):
    effective = get_effective_property_verifications(kind=kind, at=at).filter(property_id=OuterRef("pk"))
    return queryset.annotate(_has_effective_verification=Exists(effective)).filter(_has_effective_verification=True)


def annotate_listing_queryset_with_effective_verification_level(queryset, *, at=None):
    """Annotate Listing querysets using the same persisted ladder as the evaluator."""
    now = _current_time(at)
    effective_identity = ListerIdentity.objects.filter(
        user_id=OuterRef("lister_id"),
        status=ListerIdentity.Status.APPROVED,
        expires_at__isnull=False,
        expires_at__gt=now,
    )
    effective_document = get_effective_property_verifications(
        kind=PropertyVerification.Kind.DOCUMENT,
        at=now,
    ).filter(property_id=OuterRef("property_id"))
    effective_field = get_effective_property_verifications(
        kind=PropertyVerification.Kind.FIELD,
        at=now,
    ).filter(property_id=OuterRef("property_id"))

    return queryset.annotate(
        _has_effective_identity=Exists(effective_identity),
        _has_effective_document=Exists(effective_document),
        _has_effective_field=Exists(effective_field),
    ).annotate(
        effective_verification_level=Case(
            When(
                _has_effective_identity=True,
                _has_effective_document=True,
                _has_effective_field=True,
                then=Value(3),
            ),
            When(_has_effective_identity=True, _has_effective_document=True, then=Value(2)),
            When(_has_effective_identity=True, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        )
    )


def filter_listing_queryset_by_minimum_effective_verification_level(queryset, *, minimum_level, at=None):
    if minimum_level not in {0, 1, 2, 3}:
        raise ValueError("minimum_level must be between 0 and 3.")
    if "effective_verification_level" not in queryset.query.annotations:
        queryset = annotate_listing_queryset_with_effective_verification_level(queryset, at=at)
    if minimum_level:
        return queryset.filter(effective_verification_level__gte=minimum_level)
    return queryset


@transaction.atomic
def submit_document_verification(*, property_record, submitted_by, evidence, request=None):
    locked_property = _property_for_submission(property_record)
    submitter = _require_document_submitter(submitted_by, locked_property)
    evidence_items = _normalize_document_evidence(evidence)

    if PropertyVerification.objects.select_for_update().filter(
        property=locked_property,
        kind=PropertyVerification.Kind.DOCUMENT,
        status__in=[PropertyVerification.Status.PENDING, PropertyVerification.Status.APPROVED],
    ).exists():
        raise ValidationError("An active document verification already exists for this property.")

    try:
        verification = PropertyVerification.objects.create(
            property=locked_property,
            kind=PropertyVerification.Kind.DOCUMENT,
            status=PropertyVerification.Status.PENDING,
            submitted_by=submitter,
            submitted_at=timezone.now(),
            subject_snapshot=_subject_snapshot(locked_property),
        )
    except IntegrityError as exc:
        raise ValidationError("An active document verification already exists for this property.") from exc

    PropertyVerificationEvidence.objects.bulk_create([
        PropertyVerificationEvidence(
            verification=verification,
            evidence_type=item["evidence_type"],
            evidence_ref=item["evidence_ref"],
            created_by=submitter,
        )
        for item in evidence_items
    ])
    _audit_transition(
        action=VERIFICATION_DOCUMENT_SUBMITTED,
        actor=submitter,
        verification=verification,
        before={},
        request=request,
    )
    return verification


@transaction.atomic
def submit_field_verification(*, property_record, submitted_by, evidence, request=None):
    locked_property = _property_for_submission(property_record)
    submitter = _require_field_submitter(submitted_by, locked_property)
    evidence_items = _normalize_field_evidence(evidence)

    if PropertyVerification.objects.select_for_update().filter(
        property=locked_property,
        kind=PropertyVerification.Kind.FIELD,
        status__in=[PropertyVerification.Status.PENDING, PropertyVerification.Status.APPROVED],
    ).exists():
        raise ValidationError("An active field verification already exists for this property.")

    try:
        verification = PropertyVerification.objects.create(
            property=locked_property,
            kind=PropertyVerification.Kind.FIELD,
            status=PropertyVerification.Status.PENDING,
            submitted_by=submitter,
            submitted_at=timezone.now(),
            subject_snapshot=_subject_snapshot(locked_property),
        )
    except IntegrityError as exc:
        raise ValidationError("An active field verification already exists for this property.") from exc

    PropertyVerificationEvidence.objects.bulk_create([
        PropertyVerificationEvidence(
            verification=verification,
            evidence_type=item["evidence_type"],
            evidence_ref=item["evidence_ref"],
            created_by=submitter,
        )
        for item in evidence_items
    ])
    _audit_transition(
        action=VERIFICATION_FIELD_SUBMITTED,
        actor=submitter,
        verification=verification,
        before={},
        request=request,
    )
    return verification


@transaction.atomic
def approve_document_verification(*, verification, reviewer, request=None):
    reviewer = _require_document_verifier(reviewer)
    document = _document_verification_for_update(verification)
    if document.status != PropertyVerification.Status.PENDING:
        raise ValidationError("Only pending document verification can be approved.")
    if document.submitted_by_id == reviewer.pk:
        raise PermissionDenied("A submitter cannot review their own property verification.")
    if not has_effective_lister_identity(user=document.submitted_by):
        raise ValidationError("The submitter no longer has an effective Level 1 identity.")
    if not document.evidence.filter(evidence_type=PropertyVerificationEvidence.EvidenceType.TITLE_DOCUMENT).exists():
        raise ValidationError("Document verification requires title document evidence.")

    before = _audit_state(document)
    reviewed_at = timezone.now()
    document.status = PropertyVerification.Status.APPROVED
    document.reviewed_by = reviewer
    document.reviewed_at = reviewed_at
    document.expires_at = calculate_document_verification_expires_at(reviewed_at)
    document.rejection_reason = None
    document.revoked_at = None
    document.save(update_fields=[
        "status", "reviewed_by", "reviewed_at", "expires_at", "rejection_reason", "revoked_at", "updated_at",
    ])
    _audit_transition(
        action=VERIFICATION_DOCUMENT_APPROVED,
        actor=reviewer,
        verification=document,
        before=before,
        request=request,
    )
    return document


@transaction.atomic
def approve_field_verification(*, verification, reviewer, request=None):
    field = _field_verification_for_update(verification)
    reviewer = _require_field_reviewer(reviewer, field)
    if field.status != PropertyVerification.Status.PENDING:
        raise ValidationError("Only pending field verification can be approved.")
    if field.submitted_by_id == reviewer.pk:
        raise PermissionDenied("A submitter cannot review their own property verification.")
    if get_effective_verification_level(user=field.submitted_by, property_record=field.property) < 2:
        raise ValidationError("The submitter no longer has an effective Level 2 property verification.")
    if not field.evidence.filter(
        evidence_type__in=[
            PropertyVerificationEvidence.EvidenceType.FIELD_REPORT,
            PropertyVerificationEvidence.EvidenceType.OFFICIAL_ATTESTATION,
        ]
    ).exists():
        raise ValidationError("Field verification requires field or official evidence.")

    before = _audit_state(field)
    reviewed_at = timezone.now()
    field.status = PropertyVerification.Status.APPROVED
    field.reviewed_by = reviewer
    field.reviewed_at = reviewed_at
    field.expires_at = calculate_field_verification_expires_at(reviewed_at)
    field.rejection_reason = None
    field.revoked_at = None
    field.save(update_fields=[
        "status", "reviewed_by", "reviewed_at", "expires_at", "rejection_reason", "revoked_at", "updated_at",
    ])
    _audit_transition(
        action=VERIFICATION_FIELD_APPROVED,
        actor=reviewer,
        verification=field,
        before=before,
        request=request,
    )
    return field


@transaction.atomic
def reject_document_verification(*, verification, reviewer, reason, request=None):
    reviewer = _require_document_verifier(reviewer)
    document = _document_verification_for_update(verification)
    if document.status != PropertyVerification.Status.PENDING:
        raise ValidationError("Only pending document verification can be rejected.")
    if document.submitted_by_id == reviewer.pk:
        raise PermissionDenied("A submitter cannot review their own property verification.")

    before = _audit_state(document)
    document.status = PropertyVerification.Status.REJECTED
    document.reviewed_by = reviewer
    document.reviewed_at = timezone.now()
    document.expires_at = None
    document.rejection_reason = _normalize_rejection_reason(reason)
    document.revoked_at = None
    document.save(update_fields=[
        "status", "reviewed_by", "reviewed_at", "expires_at", "rejection_reason", "revoked_at", "updated_at",
    ])
    _audit_transition(
        action=VERIFICATION_DOCUMENT_REJECTED,
        actor=reviewer,
        verification=document,
        before=before,
        request=request,
    )
    return document


@transaction.atomic
def reject_field_verification(*, verification, reviewer, reason, request=None):
    field = _field_verification_for_update(verification)
    reviewer = _require_field_reviewer(reviewer, field)
    if field.status != PropertyVerification.Status.PENDING:
        raise ValidationError("Only pending field verification can be rejected.")
    if field.submitted_by_id == reviewer.pk:
        raise PermissionDenied("A submitter cannot review their own property verification.")

    before = _audit_state(field)
    field.status = PropertyVerification.Status.REJECTED
    field.reviewed_by = reviewer
    field.reviewed_at = timezone.now()
    field.expires_at = None
    field.rejection_reason = _normalize_rejection_reason(reason)
    field.revoked_at = None
    field.save(update_fields=[
        "status", "reviewed_by", "reviewed_at", "expires_at", "rejection_reason", "revoked_at", "updated_at",
    ])
    _audit_transition(
        action=VERIFICATION_FIELD_REJECTED,
        actor=reviewer,
        verification=field,
        before=before,
        request=request,
    )
    return field


@transaction.atomic
def revoke_document_verification(*, verification, reviewer, request=None):
    reviewer = _require_document_verifier(reviewer)
    document = _document_verification_for_update(verification)
    if document.status != PropertyVerification.Status.APPROVED:
        raise ValidationError("Only approved document verification can be revoked.")

    before = _audit_state(document)
    document.status = PropertyVerification.Status.REVOKED
    document.revoked_at = timezone.now()
    document.save(update_fields=["status", "revoked_at", "updated_at"])
    _audit_transition(
        action=VERIFICATION_DOCUMENT_REVOKED,
        actor=reviewer,
        verification=document,
        before=before,
        request=request,
    )
    return document


@transaction.atomic
def revoke_field_verification(*, verification, reviewer, request=None):
    field = _field_verification_for_update(verification)
    reviewer = _require_field_reviewer(reviewer, field)
    if field.status != PropertyVerification.Status.APPROVED:
        raise ValidationError("Only approved field verification can be revoked.")

    before = _audit_state(field)
    field.status = PropertyVerification.Status.REVOKED
    field.revoked_at = timezone.now()
    field.save(update_fields=["status", "revoked_at", "updated_at"])
    _audit_transition(
        action=VERIFICATION_FIELD_REVOKED,
        actor=reviewer,
        verification=field,
        before=before,
        request=request,
    )
    return field


@transaction.atomic
def expire_document_verifications(*, at=None):
    now = _current_time(at)
    due_documents = list(
        PropertyVerification.objects.select_for_update()
        .select_related("property")
        .filter(
            kind=PropertyVerification.Kind.DOCUMENT,
            status=PropertyVerification.Status.APPROVED,
            expires_at__isnull=False,
            expires_at__lte=now,
        )
        .order_by("expires_at", "id")
    )
    for document in due_documents:
        before = _audit_state(document)
        document.status = PropertyVerification.Status.EXPIRED
        document.save(update_fields=["status", "updated_at"])
        _audit_transition(
            action=VERIFICATION_DOCUMENT_EXPIRED,
            actor=None,
            verification=document,
            before=before,
        )
    return len(due_documents)


@transaction.atomic
def expire_field_verifications(*, at=None):
    now = _current_time(at)
    due_fields = list(
        PropertyVerification.objects.select_for_update()
        .select_related("property")
        .filter(
            kind=PropertyVerification.Kind.FIELD,
            status=PropertyVerification.Status.APPROVED,
            expires_at__isnull=False,
            expires_at__lte=now,
        )
        .order_by("expires_at", "id")
    )
    for field in due_fields:
        before = _audit_state(field)
        field.status = PropertyVerification.Status.EXPIRED
        field.save(update_fields=["status", "updated_at"])
        _audit_transition(
            action=VERIFICATION_FIELD_EXPIRED,
            actor=None,
            verification=field,
            before=before,
        )
    return len(due_fields)


def expire_property_verifications(*, at=None):
    return expire_document_verifications(at=at) + expire_field_verifications(at=at)


def get_effective_verification_level(*, user, property_record=None, at=None):
    now = _current_time(at)
    if not has_effective_lister_identity(user=user, at=now):
        return 0
    if property_record is None:
        return 1

    document_verifications = get_effective_property_verifications(
        kind=PropertyVerification.Kind.DOCUMENT,
        at=now,
    ).filter(property=property_record)
    if not document_verifications.exists():
        return 1

    field_verifications = get_effective_property_verifications(
        kind=PropertyVerification.Kind.FIELD,
        at=now,
    ).filter(property=property_record)
    return 3 if field_verifications.exists() else 2
