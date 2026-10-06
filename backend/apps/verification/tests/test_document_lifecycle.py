from datetime import timedelta
from decimal import Decimal
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import override_settings
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.models import AuditLog
from apps.lister_identity.models import ListerIdentity
from apps.localities.models import District, Locality, Region, Ward
from apps.properties.models import PropertyRecord
from apps.roles.catalog import ROLE_MANAGEMENT, ROLE_OWNER, ROLE_VERIFIER
from apps.roles.models import Role, UserRole
from apps.roles.services import bootstrap_canonical_roles
from apps.verification.audit_events import (
    VERIFICATION_DOCUMENT_APPROVED,
    VERIFICATION_DOCUMENT_EXPIRED,
    VERIFICATION_DOCUMENT_REJECTED,
    VERIFICATION_DOCUMENT_REVOKED,
    VERIFICATION_DOCUMENT_SUBMITTED,
)
from apps.verification.models import PropertyVerification, PropertyVerificationEvidence
from apps.verification.services import (
    approve_document_verification,
    expire_document_verifications,
    get_effective_verification_level,
    reject_document_verification,
    revoke_document_verification,
    submit_document_verification,
)


pytestmark = pytest.mark.django_db

PRIVATE_EVIDENCE = "private/document-secret-reference"
PRIVATE_REASON = "private rejection rationale"


def create_user():
    token = uuid.uuid4().hex[:12]
    return get_user_model().objects.create_user(
        email=f"document-verification-{token}@example.test",
        phone=f"+2557{int(token[:8], 16) % 100000000:08d}",
        full_name="Document Verification User",
        password="StrongPass123!",
    )


def grant_role(user, role_code, *, active=True):
    bootstrap_canonical_roles()
    return UserRole.objects.create(user=user, role=Role.objects.get(code=role_code), is_active=active)


def owner_with_level_one():
    user = create_user()
    grant_role(user, ROLE_OWNER)
    ListerIdentity.objects.create(
        user=user,
        national_id_number="NIDA-DOCUMENT-TEST",
        national_id_photo_ref="private/id-document",
        live_selfie_ref="private/selfie-document",
        status=ListerIdentity.Status.APPROVED,
        expires_at=timezone.now() + timedelta(days=30),
    )
    return user


def create_property(owner):
    token = uuid.uuid4().hex[:10]
    region = Region.objects.create(name=f"Document {token} Region")
    district = District.objects.create(region=region, name=f"Document {token} District")
    ward = Ward.objects.create(district=district, name=f"Document {token} Ward")
    locality = Locality.objects.create(
        ward=ward,
        name=f"Document {token} Street",
        kind=Locality.Kind.STREET,
        approved=True,
    )
    return PropertyRecord.objects.create(
        property_id=f"OWR-{uuid.uuid4().hex[:16].upper()}",
        category=PropertyRecord.Category.LAND,
        pin=Point(39.2083, -6.7924, srid=4326),
        region=region,
        district=district,
        ward=ward,
        locality=locality,
        stated_size=Decimal("1200.00"),
        size_unit="sqm",
        title_type=PropertyRecord.TitleType.UNKNOWN,
        created_by=owner,
    )


def document_evidence(reference=PRIVATE_EVIDENCE):
    return [{
        "evidence_type": PropertyVerificationEvidence.EvidenceType.TITLE_DOCUMENT,
        "evidence_ref": reference,
    }]


def verifier(*, active=True):
    user = create_user()
    grant_role(user, ROLE_VERIFIER, active=active)
    return user


def submit_ready_document():
    owner = owner_with_level_one()
    property_record = create_property(owner)
    verification = submit_document_verification(
        property_record=property_record,
        submitted_by=owner,
        evidence=document_evidence(),
    )
    return owner, property_record, verification


def test_level_one_property_actor_can_submit_pending_document_with_private_evidence():
    owner, property_record, verification = submit_ready_document()

    assert verification.property == property_record
    assert verification.submitted_by == owner
    assert verification.kind == PropertyVerification.Kind.DOCUMENT
    assert verification.status == PropertyVerification.Status.PENDING
    assert verification.reviewed_by is None
    assert verification.expires_at is None
    assert verification.evidence.get().evidence_ref == PRIVATE_EVIDENCE
    assert verification.subject_snapshot["property_id"] == property_record.property_id
    assert "pin" not in verification.subject_snapshot


def test_submission_requires_level_one_property_access_valid_evidence_and_no_active_duplicate():
    owner = owner_with_level_one()
    property_record = create_property(owner)
    owner.lister_identity.expires_at = timezone.now() - timedelta(seconds=1)
    owner.lister_identity.save(update_fields=["expires_at", "updated_at"])
    with pytest.raises(ValidationError):
        submit_document_verification(property_record=property_record, submitted_by=owner, evidence=document_evidence())

    owner.lister_identity.expires_at = timezone.now() + timedelta(days=30)
    owner.lister_identity.save(update_fields=["expires_at", "updated_at"])
    other_owner = owner_with_level_one()
    with pytest.raises(PermissionDenied):
        submit_document_verification(property_record=property_record, submitted_by=other_owner, evidence=document_evidence())
    with pytest.raises(ValidationError):
        submit_document_verification(property_record=property_record, submitted_by=owner, evidence=document_evidence("https://example.test/doc"))
    for unsafe_reference in ("../private/document", "/private/document", r"C:\\private\\document", "a" * 128 + "=="):
        with pytest.raises(ValidationError):
            submit_document_verification(
                property_record=property_record,
                submitted_by=owner,
                evidence=document_evidence(unsafe_reference),
            )

    submit_document_verification(property_record=property_record, submitted_by=owner, evidence=document_evidence())
    with pytest.raises(ValidationError):
        submit_document_verification(property_record=property_record, submitted_by=owner, evidence=document_evidence("private/second-document"))


def test_approval_requires_active_canonical_verifier_and_server_generates_expiry():
    owner, property_record, verification = submit_ready_document()
    manager = create_user()
    grant_role(manager, ROLE_MANAGEMENT)
    inactive_verifier = verifier(active=False)
    fake_verifier = create_user()
    fake_verifier.role = ROLE_VERIFIER
    fake_verifier.verification_claim = "VERIFIER"

    for reviewer in (manager, inactive_verifier, fake_verifier):
        with pytest.raises(PermissionDenied):
            approve_document_verification(verification=verification, reviewer=reviewer)

    with override_settings(PROPERTY_DOCUMENT_VERIFICATION_VALIDITY_MONTHS=2):
        approved_at_before = timezone.now()
        approved = approve_document_verification(verification=verification, reviewer=verifier())

    assert approved.status == PropertyVerification.Status.APPROVED
    assert approved.reviewed_by is not None
    assert approved.reviewed_at is not None
    assert approved.expires_at > approved_at_before + timedelta(days=55)
    assert approved.expires_at < approved_at_before + timedelta(days=65)
    assert get_effective_verification_level(user=owner, property_record=property_record) == 2


def test_approval_rejects_non_pending_and_missing_or_expired_level_one():
    owner, _, verification = submit_ready_document()
    reviewer = verifier()
    approve_document_verification(verification=verification, reviewer=reviewer)
    with pytest.raises(ValidationError):
        approve_document_verification(verification=verification, reviewer=reviewer)

    owner, _, verification = submit_ready_document()
    owner.lister_identity.expires_at = timezone.now() - timedelta(seconds=1)
    owner.lister_identity.save(update_fields=["expires_at", "updated_at"])
    with pytest.raises(ValidationError):
        approve_document_verification(verification=verification, reviewer=reviewer)


def test_rejection_requires_active_verifier_and_non_blank_bounded_reason():
    _, _, verification = submit_ready_document()
    with pytest.raises(ValidationError):
        reject_document_verification(verification=verification, reviewer=verifier(), reason="   ")
    with pytest.raises(PermissionDenied):
        reject_document_verification(verification=verification, reviewer=create_user(), reason="Missing proof")

    rejected = reject_document_verification(verification=verification, reviewer=verifier(), reason=PRIVATE_REASON)

    assert rejected.status == PropertyVerification.Status.REJECTED
    assert rejected.reviewed_by is not None
    assert rejected.reviewed_at is not None
    assert rejected.rejection_reason == PRIVATE_REASON


def test_approved_document_can_be_revoked_without_losing_history_or_evidence():
    owner, property_record, verification = submit_ready_document()
    with pytest.raises(ValidationError):
        revoke_document_verification(verification=verification, reviewer=verifier())
    approved = approve_document_verification(verification=verification, reviewer=verifier())
    evidence_id = approved.evidence.get().pk

    revoked = revoke_document_verification(verification=approved, reviewer=verifier())

    assert revoked.status == PropertyVerification.Status.REVOKED
    assert revoked.revoked_at is not None
    assert PropertyVerificationEvidence.objects.filter(pk=evidence_id, verification=revoked).exists()
    assert get_effective_verification_level(user=owner, property_record=property_record) == 1
    with pytest.raises(ValidationError):
        revoke_document_verification(verification=revoked, reviewer=verifier())


def test_expiry_is_idempotent_and_only_transitions_due_approved_documents():
    _, _, due = submit_ready_document()
    approve_document_verification(verification=due, reviewer=verifier())
    due.expires_at = timezone.now() - timedelta(seconds=1)
    due.save(update_fields=["expires_at", "updated_at"])

    _, _, future = submit_ready_document()
    approve_document_verification(verification=future, reviewer=verifier())

    assert expire_document_verifications() == 1
    due.refresh_from_db()
    future.refresh_from_db()
    assert due.status == PropertyVerification.Status.EXPIRED
    assert future.status == PropertyVerification.Status.APPROVED
    assert expire_document_verifications() == 0


def test_document_lifecycle_audits_safe_transition_metadata_only():
    _, _, submitted = submit_ready_document()
    approved = approve_document_verification(verification=submitted, reviewer=verifier())
    revoke_document_verification(verification=approved, reviewer=verifier())

    _, _, rejected = submit_ready_document()
    reject_document_verification(verification=rejected, reviewer=verifier(), reason=PRIVATE_REASON)

    _, _, expiring = submit_ready_document()
    expiring = approve_document_verification(verification=expiring, reviewer=verifier())
    expiring.expires_at = timezone.now() - timedelta(seconds=1)
    expiring.save(update_fields=["expires_at", "updated_at"])
    expire_document_verifications()

    actions = {
        VERIFICATION_DOCUMENT_SUBMITTED,
        VERIFICATION_DOCUMENT_APPROVED,
        VERIFICATION_DOCUMENT_REJECTED,
        VERIFICATION_DOCUMENT_REVOKED,
        VERIFICATION_DOCUMENT_EXPIRED,
    }
    logs = AuditLog.objects.filter(action__in=actions)
    assert {log.action for log in logs} == actions
    assert AuditLog.objects.filter(action=VERIFICATION_DOCUMENT_APPROVED, entity_id=str(approved.pk)).count() == 1
    assert AuditLog.objects.filter(action=VERIFICATION_DOCUMENT_REVOKED, entity_id=str(approved.pk)).count() == 1
    assert AuditLog.objects.filter(action=VERIFICATION_DOCUMENT_REJECTED, entity_id=str(rejected.pk)).count() == 1
    assert AuditLog.objects.filter(action=VERIFICATION_DOCUMENT_EXPIRED, entity_id=str(expiring.pk)).count() == 1
    for log in logs:
        assert set(log.after) == {"property_id", "verification_id", "kind", "status"}
        rendered = repr(log.before) + repr(log.after)
        assert PRIVATE_EVIDENCE not in rendered
        assert PRIVATE_REASON not in rendered
