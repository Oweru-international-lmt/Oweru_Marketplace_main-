import calendar
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.audit.services import create_audit_log
from apps.roles.catalog import ROLE_AGENT, ROLE_MANAGEMENT, ROLE_OWNER
from apps.roles.services import user_has_role

from .audit_events import (
    LISTER_IDENTITY_APPROVED,
    LISTER_IDENTITY_CREATED,
    LISTER_IDENTITY_EXPIRED,
    LISTER_IDENTITY_REJECTED,
    LISTER_IDENTITY_SUBMITTED,
    LISTER_IDENTITY_UPDATED,
)
from .evidence import normalize_identity_evidence_attrs, validate_submission_evidence
from .models import ListerIdentity


WRITABLE_IDENTITY_FIELDS = frozenset({"national_id_number", "national_id_photo_ref", "live_selfie_ref"})
LISTER_IDENTITY_AUDIT_ENTITY = "ListerIdentity"
PUBLIC_VERIFICATION_LEVEL_0 = 0
PUBLIC_VERIFICATION_LEVEL_1 = 1
PUBLIC_VERIFICATION_LEVEL_2 = 2
PUBLIC_VERIFICATION_LEVEL_3 = 3
PUBLIC_VERIFICATION_UNVERIFIED_LABEL = "Not verified"
PUBLIC_VERIFICATION_IDENTITY_LABEL = "Identity verified"
PUBLIC_VERIFICATION_PROPERTY_LABEL = "Property verified"
PUBLIC_VERIFICATION_FIELD_LABEL = "Field verified"
PUBLIC_VERIFICATION_LABELS = {
    PUBLIC_VERIFICATION_LEVEL_0: PUBLIC_VERIFICATION_UNVERIFIED_LABEL,
    PUBLIC_VERIFICATION_LEVEL_1: PUBLIC_VERIFICATION_IDENTITY_LABEL,
    PUBLIC_VERIFICATION_LEVEL_2: PUBLIC_VERIFICATION_PROPERTY_LABEL,
    PUBLIC_VERIFICATION_LEVEL_3: PUBLIC_VERIFICATION_FIELD_LABEL,
}


def _require_persisted_lister(user):
    if user is None or not getattr(user, "is_authenticated", False):
        raise PermissionDenied("Authentication is required.")
    if not getattr(user, "pk", None):
        raise PermissionDenied("A persisted account is required.")
    if not (user_has_role(user, ROLE_OWNER) or user_has_role(user, ROLE_AGENT)):
        raise PermissionDenied("An active Owner or Agent role is required.")
    return user


def _require_persisted_management(user):
    if user is None or not getattr(user, "is_authenticated", False):
        raise PermissionDenied("Authentication is required.")
    if not getattr(user, "pk", None):
        raise PermissionDenied("A persisted management account is required.")
    if not user_has_role(user, ROLE_MANAGEMENT):
        raise PermissionDenied("An active Management role is required.")
    return user


def _identity_queryset():
    return ListerIdentity.objects.select_for_update(of=("self",)).select_related("user", "reviewed_by")


def _own_identity_for_update(user):
    try:
        return _identity_queryset().get(user=user)
    except ListerIdentity.DoesNotExist as exc:
        raise NotFound("Lister identity was not found.") from exc


def _normalize_identity_attrs(attrs):
    return normalize_identity_evidence_attrs({
        field: attrs[field] for field in WRITABLE_IDENTITY_FIELDS if field in attrs
    })


def _ensure_self_owned(identity, user):
    if identity.user_id != user.pk:
        raise PermissionDenied("You can manage only your own lister identity.")


def _ensure_editable(identity):
    if identity.status != ListerIdentity.Status.PENDING or identity.submitted_at is not None:
        raise ValidationError("Submitted or reviewed lister identities cannot be edited.")


def _identity_for_review(identity):
    identity_id = identity.pk if isinstance(identity, ListerIdentity) else identity
    try:
        return _identity_queryset().get(pk=identity_id)
    except ListerIdentity.DoesNotExist as exc:
        raise NotFound("Lister identity was not found.") from exc


def _ensure_reviewable(identity, actor):
    if identity.user_id == actor.pk:
        raise PermissionDenied("You cannot review your own lister identity.")
    if identity.status != ListerIdentity.Status.PENDING or identity.submitted_at is None:
        raise ValidationError("Lister identity is not awaiting management review.")


def _normalize_rejection_reason(reason):
    if reason is None or not isinstance(reason, str):
        raise ValidationError({"reason": "Rejection reason is required."})
    normalized = reason.strip()
    if not normalized:
        raise ValidationError({"reason": "Rejection reason is required."})
    return normalized


def _current_time(at=None):
    return at or timezone.now()


def add_calendar_months(value, months):
    total_months = value.month - 1 + months
    year = value.year + total_months // 12
    month = total_months % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def calculate_lister_identity_expires_at(approved_at):
    return add_calendar_months(approved_at, settings.LISTER_IDENTITY_VALIDITY_MONTHS)


def _iso(value):
    return value.isoformat() if value is not None else None


def _audit_state(identity):
    return {
        "identity_id": str(identity.pk),
        "user_id": str(identity.user_id),
        "status": identity.status,
        "submitted_at": _iso(identity.submitted_at),
        "reviewed_at": _iso(identity.reviewed_at),
        "reviewed_by_id": str(identity.reviewed_by_id) if identity.reviewed_by_id else None,
        "expires_at": _iso(identity.expires_at),
    }


def _changed_field_flags(changed_fields):
    return {
        "identity_id": "",
        "national_id_changed": "national_id_number" in changed_fields,
        "id_photo_ref_changed": "national_id_photo_ref" in changed_fields,
        "selfie_ref_changed": "live_selfie_ref" in changed_fields,
    }


def get_lister_identity(*, user):
    _require_persisted_lister(user)
    try:
        return ListerIdentity.objects.select_related("user", "reviewed_by").get(user=user)
    except ListerIdentity.DoesNotExist as exc:
        raise NotFound("Lister identity was not found.") from exc


@transaction.atomic
def create_lister_identity(*, user, request=None, **attrs):
    user = _require_persisted_lister(user)
    values = _normalize_identity_attrs(attrs)
    values.setdefault("national_id_number", "")
    values.setdefault("national_id_photo_ref", "")
    values.setdefault("live_selfie_ref", "")

    if ListerIdentity.objects.select_for_update().filter(user=user).exists():
        raise ValidationError("A lister identity already exists for this account.")

    try:
        identity = ListerIdentity.objects.create(
            user=user,
            status=ListerIdentity.Status.PENDING,
            submitted_at=None,
            reviewed_at=None,
            reviewed_by=None,
            review_reason="",
            expires_at=None,
            **values,
        )
        create_audit_log(
            actor=user,
            action=LISTER_IDENTITY_CREATED,
            entity_type=LISTER_IDENTITY_AUDIT_ENTITY,
            entity_id=identity.pk,
            before={},
            after=_audit_state(identity),
            request=request,
        )
        return identity
    except IntegrityError as exc:
        raise ValidationError("A lister identity already exists for this account.") from exc


@transaction.atomic
def update_lister_identity(*, user, identity=None, request=None, **attrs):
    user = _require_persisted_lister(user)
    identity = _own_identity_for_update(user) if identity is None else _identity_queryset().get(pk=identity.pk)
    _ensure_self_owned(identity, user)
    _ensure_editable(identity)

    values = _normalize_identity_attrs(attrs)
    changed_fields = [field for field, value in values.items() if getattr(identity, field) != value]
    for field, value in values.items():
        setattr(identity, field, value)
    if changed_fields:
        identity.save(update_fields=[*changed_fields, "updated_at"])
        after = _changed_field_flags(changed_fields)
        after["identity_id"] = str(identity.pk)
        create_audit_log(
            actor=user,
            action=LISTER_IDENTITY_UPDATED,
            entity_type=LISTER_IDENTITY_AUDIT_ENTITY,
            entity_id=identity.pk,
            before={},
            after=after,
            request=request,
        )
    return identity


@transaction.atomic
def submit_lister_identity(*, user, identity=None, request=None):
    user = _require_persisted_lister(user)
    identity = _own_identity_for_update(user) if identity is None else _identity_queryset().get(pk=identity.pk)
    _ensure_self_owned(identity, user)
    if identity.status != ListerIdentity.Status.PENDING or identity.submitted_at is not None:
        raise ValidationError("Lister identity has already been submitted.")

    before = _audit_state(identity)
    normalized_evidence = validate_submission_evidence(identity)
    for field, value in normalized_evidence.items():
        setattr(identity, field, value)

    identity.submitted_at = timezone.now()
    identity.save(update_fields=[*normalized_evidence.keys(), "submitted_at", "updated_at"])
    create_audit_log(
        actor=user,
        action=LISTER_IDENTITY_SUBMITTED,
        entity_type=LISTER_IDENTITY_AUDIT_ENTITY,
        entity_id=identity.pk,
        before=before,
        after=_audit_state(identity),
        request=request,
    )
    return identity


@transaction.atomic
def approve_lister_identity(*, identity, reviewed_by, request=None):
    actor = _require_persisted_management(reviewed_by)
    identity = _identity_for_review(identity)
    _ensure_reviewable(identity, actor)
    validate_submission_evidence(identity)
    before = _audit_state(identity)
    reviewed_at = timezone.now()

    identity.status = ListerIdentity.Status.APPROVED
    identity.reviewed_at = reviewed_at
    identity.reviewed_by = actor
    identity.review_reason = ""
    identity.expires_at = calculate_lister_identity_expires_at(reviewed_at)
    identity.save(update_fields=["status", "reviewed_at", "reviewed_by", "review_reason", "expires_at", "updated_at"])
    create_audit_log(
        actor=actor,
        action=LISTER_IDENTITY_APPROVED,
        entity_type=LISTER_IDENTITY_AUDIT_ENTITY,
        entity_id=identity.pk,
        before=before,
        after=_audit_state(identity),
        request=request,
    )
    return identity


@transaction.atomic
def reject_lister_identity(*, identity, reviewed_by, reason, request=None):
    actor = _require_persisted_management(reviewed_by)
    identity = _identity_for_review(identity)
    _ensure_reviewable(identity, actor)
    normalized_reason = _normalize_rejection_reason(reason)
    before = _audit_state(identity)

    identity.status = ListerIdentity.Status.REJECTED
    identity.reviewed_at = timezone.now()
    identity.reviewed_by = actor
    identity.review_reason = normalized_reason
    identity.expires_at = None
    identity.save(update_fields=["status", "reviewed_at", "reviewed_by", "review_reason", "expires_at", "updated_at"])
    after = _audit_state(identity)
    after["reason_present"] = True
    create_audit_log(
        actor=actor,
        action=LISTER_IDENTITY_REJECTED,
        entity_type=LISTER_IDENTITY_AUDIT_ENTITY,
        entity_id=identity.pk,
        before=before,
        after=after,
        request=request,
    )
    return identity


@transaction.atomic
def expire_lister_identities(*, at=None):
    now = _current_time(at)
    due_identities = list(
        ListerIdentity.objects.select_for_update()
        .filter(status=ListerIdentity.Status.APPROVED, expires_at__isnull=False, expires_at__lte=now)
        .order_by("expires_at", "id")
    )
    expired_count = 0
    for identity in due_identities:
        before = _audit_state(identity)
        identity.status = ListerIdentity.Status.EXPIRED
        identity.save(update_fields=["status", "updated_at"])
        create_audit_log(
            actor=None,
            action=LISTER_IDENTITY_EXPIRED,
            entity_type=LISTER_IDENTITY_AUDIT_ENTITY,
            entity_id=identity.pk,
            before=before,
            after=_audit_state(identity),
        )
        expired_count += 1
    return expired_count


def get_lister_identities_due_for_expiry_reminder(*, at=None):
    now = _current_time(at)
    reminder_cutoff = now + timedelta(days=settings.LISTER_IDENTITY_EXPIRY_REMINDER_DAYS)
    return (
        ListerIdentity.objects.select_related("user", "reviewed_by")
        .filter(
            status=ListerIdentity.Status.APPROVED,
            expires_at__isnull=False,
            expires_at__gt=now,
            expires_at__lte=reminder_cutoff,
        )
        .order_by("expires_at", "id")
    )


def is_lister_identity_verified(identity, *, at=None):
    now = _current_time(at)
    return bool(
        identity
        and identity.status == ListerIdentity.Status.APPROVED
        and identity.expires_at is not None
        and identity.expires_at > now
    )


def get_public_verification_summary(*, user=None, identity=None, property_record=None, listing=None, at=None):
    """Compatibility presentation wrapper over the canonical verification engine."""
    if listing is not None and hasattr(listing, "effective_verification_level"):
        level = listing.effective_verification_level
    else:
        from apps.verification.services import get_effective_verification_level

        if user is None and isinstance(identity, ListerIdentity) and identity.pk:
            user = identity.user
        level = get_effective_verification_level(user=user, property_record=property_record, at=at)
    if level not in PUBLIC_VERIFICATION_LABELS:
        raise ValueError("Verification level must be canonical.")
    return {
        "level": level,
        "label": PUBLIC_VERIFICATION_LABELS[level],
        "is_verified": level > PUBLIC_VERIFICATION_LEVEL_0,
    }


def get_public_lister_roles(user):
    roles = []
    if user_has_role(user, ROLE_OWNER):
        roles.append(ROLE_OWNER)
    if user_has_role(user, ROLE_AGENT):
        roles.append(ROLE_AGENT)
    return roles


def get_public_lister_identity(*, identity_id, at=None):
    try:
        identity = ListerIdentity.objects.select_related("user").get(pk=identity_id)
    except ListerIdentity.DoesNotExist as exc:
        raise NotFound("Lister profile was not found.") from exc

    if not identity.user.is_active or not is_lister_identity_verified(identity, at=at):
        raise NotFound("Lister profile was not found.")

    lister_roles = get_public_lister_roles(identity.user)
    if not lister_roles:
        raise NotFound("Lister profile was not found.")
    return identity, lister_roles
