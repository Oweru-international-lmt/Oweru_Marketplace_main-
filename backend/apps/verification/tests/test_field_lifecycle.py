from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.models import AuditLog
from apps.local_officials.models import OfficialJurisdictionAssignment
from apps.local_officials.services import assign_jurisdiction, create_local_official_profile
from apps.localities.models import Region
from apps.roles.catalog import ROLE_LOCAL_OFFICIAL, ROLE_MANAGEMENT, ROLE_VERIFIER
from apps.verification.audit_events import (
    VERIFICATION_FIELD_APPROVED,
    VERIFICATION_FIELD_EXPIRED,
    VERIFICATION_FIELD_REJECTED,
    VERIFICATION_FIELD_REVOKED,
    VERIFICATION_FIELD_SUBMITTED,
)
from apps.verification.models import PropertyVerification, PropertyVerificationEvidence
from apps.verification.services import (
    approve_document_verification,
    approve_field_verification,
    expire_field_verifications,
    get_effective_verification_level,
    reject_field_verification,
    revoke_document_verification,
    revoke_field_verification,
    submit_document_verification,
    submit_field_verification,
)

from .test_document_lifecycle import create_property, create_user, document_evidence, grant_role, owner_with_level_one, verifier


pytestmark = pytest.mark.django_db

PRIVATE_FIELD_EVIDENCE = "private/field-report-secret"
PRIVATE_REASON = "private field rejection rationale"


def field_evidence(reference=PRIVATE_FIELD_EVIDENCE):
    return [{
        "evidence_type": PropertyVerificationEvidence.EvidenceType.FIELD_REPORT,
        "evidence_ref": reference,
    }]


def local_official(*, active=True):
    user = create_user()
    grant_role(user, ROLE_LOCAL_OFFICIAL, active=active)
    if active:
        manager = create_user()
        grant_role(manager, ROLE_MANAGEMENT)
        profile = create_local_official_profile(
            actor=manager,
            user=user,
            official_number=f"LO-{user.pk.hex[:12].upper()}",
        )
        for region in Region.objects.all():
            assign_jurisdiction(
                actor=manager,
                official=profile,
                scope_type=OfficialJurisdictionAssignment.ScopeType.REGION,
                region=region,
                starts_at=timezone.now() - timedelta(minutes=1),
            )
    return user


def level_two_property():
    owner = owner_with_level_one()
    property_record = create_property(owner)
    document = submit_document_verification(
        property_record=property_record,
        submitted_by=owner,
        evidence=document_evidence(),
    )
    document = approve_document_verification(verification=document, reviewer=verifier())
    return owner, property_record, document


def submitted_field():
    owner, property_record, document = level_two_property()
    field = submit_field_verification(
        property_record=property_record,
        submitted_by=owner,
        evidence=field_evidence(),
    )
    return owner, property_record, document, field


def test_effective_level_two_property_actor_can_submit_field_verification():
    owner, property_record, _, field = submitted_field()

    assert field.property == property_record
    assert field.submitted_by == owner
    assert field.kind == PropertyVerification.Kind.FIELD
    assert field.status == PropertyVerification.Status.PENDING
    assert field.evidence.get().evidence_ref == PRIVATE_FIELD_EVIDENCE
    assert "pin" not in field.subject_snapshot


def test_field_submission_requires_level_two_property_access_valid_evidence_and_no_active_duplicate():
    owner = owner_with_level_one()
    property_record = create_property(owner)
    with pytest.raises(ValidationError):
        submit_field_verification(property_record=property_record, submitted_by=owner, evidence=field_evidence())

    owner, property_record, _, _ = submitted_field()
    other_owner = owner_with_level_one()
    with pytest.raises(PermissionDenied):
        submit_field_verification(property_record=property_record, submitted_by=other_owner, evidence=field_evidence())
    with pytest.raises(ValidationError):
        submit_field_verification(
            property_record=property_record,
            submitted_by=owner,
            evidence=field_evidence("https://example.test/field-report"),
        )
    with pytest.raises(ValidationError):
        submit_field_verification(property_record=property_record, submitted_by=owner, evidence=field_evidence())


def test_field_approval_requires_active_local_official_and_generates_expiry():
    owner, property_record, _, field = submitted_field()
    management = create_user()
    grant_role(management, ROLE_MANAGEMENT)
    inactive_official = local_official(active=False)
    verifier_only = verifier()
    fake_official = create_user()
    fake_official.role = ROLE_LOCAL_OFFICIAL
    fake_official.verification_claim = "LOCAL_OFFICIAL"

    for reviewer in (management, inactive_official, verifier_only, fake_official):
        with pytest.raises(PermissionDenied):
            approve_field_verification(verification=field, reviewer=reviewer)

    with override_settings(PROPERTY_FIELD_VERIFICATION_VALIDITY_MONTHS=2):
        before = timezone.now()
        approved = approve_field_verification(verification=field, reviewer=local_official())

    assert approved.status == PropertyVerification.Status.APPROVED
    assert approved.expires_at > before + timedelta(days=55)
    assert approved.expires_at < before + timedelta(days=65)
    assert get_effective_verification_level(user=owner, property_record=property_record) == 3


def test_field_approval_rechecks_level_two_and_pending_status():
    owner, _, document, field = submitted_field()
    revoke_document_verification(verification=document, reviewer=verifier())
    with pytest.raises(ValidationError):
        approve_field_verification(verification=field, reviewer=local_official())

    _, _, _, field = submitted_field()
    official = local_official()
    approve_field_verification(verification=field, reviewer=official)
    with pytest.raises(ValidationError):
        approve_field_verification(verification=field, reviewer=official)

    assert owner.lister_identity.status == "APPROVED"


def test_field_rejection_and_revocation_preserve_history_and_evidence():
    _, _, _, pending = submitted_field()
    with pytest.raises(ValidationError):
        reject_field_verification(verification=pending, reviewer=local_official(), reason=" ")
    rejected = reject_field_verification(verification=pending, reviewer=local_official(), reason=PRIVATE_REASON)
    assert rejected.status == PropertyVerification.Status.REJECTED

    owner, property_record, _, pending = submitted_field()
    approved = approve_field_verification(verification=pending, reviewer=local_official())
    evidence_id = approved.evidence.get().pk
    revoked = revoke_field_verification(verification=approved, reviewer=local_official())

    assert revoked.status == PropertyVerification.Status.REVOKED
    assert PropertyVerificationEvidence.objects.filter(pk=evidence_id, verification=revoked).exists()
    assert get_effective_verification_level(user=owner, property_record=property_record) == 2
    with pytest.raises(ValidationError):
        revoke_field_verification(verification=revoked, reviewer=local_official())


def test_field_expiry_is_idempotent_and_level_two_cascade_remains_derived():
    owner, property_record, document, pending = submitted_field()
    approved = approve_field_verification(verification=pending, reviewer=local_official())
    approved.expires_at = timezone.now() - timedelta(seconds=1)
    approved.save(update_fields=["expires_at", "updated_at"])

    assert expire_field_verifications() == 1
    approved.refresh_from_db()
    assert approved.status == PropertyVerification.Status.EXPIRED
    assert expire_field_verifications() == 0
    assert get_effective_verification_level(user=owner, property_record=property_record) == 2

    future = submit_field_verification(
        property_record=property_record,
        submitted_by=owner,
        evidence=field_evidence("private/replacement-field-report"),
    )
    future = approve_field_verification(verification=future, reviewer=local_official())
    assert get_effective_verification_level(user=owner, property_record=property_record) == 3

    document = revoke_document_verification(verification=document, reviewer=verifier())
    future.refresh_from_db()
    assert future.status == PropertyVerification.Status.APPROVED
    assert document.status == PropertyVerification.Status.REVOKED
    assert get_effective_verification_level(user=owner, property_record=property_record) == 1

    owner.lister_identity.expires_at = timezone.now() - timedelta(seconds=1)
    owner.lister_identity.save(update_fields=["expires_at", "updated_at"])
    assert get_effective_verification_level(user=owner, property_record=property_record) == 0


def test_field_lifecycle_audits_safe_transition_metadata_only():
    _, _, _, submitted = submitted_field()
    approved = approve_field_verification(verification=submitted, reviewer=local_official())
    revoke_field_verification(verification=approved, reviewer=local_official())

    _, _, _, rejected = submitted_field()
    reject_field_verification(verification=rejected, reviewer=local_official(), reason=PRIVATE_REASON)

    _, _, _, expiring = submitted_field()
    expiring = approve_field_verification(verification=expiring, reviewer=local_official())
    expiring.expires_at = timezone.now() - timedelta(seconds=1)
    expiring.save(update_fields=["expires_at", "updated_at"])
    expire_field_verifications()

    actions = {
        VERIFICATION_FIELD_SUBMITTED,
        VERIFICATION_FIELD_APPROVED,
        VERIFICATION_FIELD_REJECTED,
        VERIFICATION_FIELD_REVOKED,
        VERIFICATION_FIELD_EXPIRED,
    }
    logs = AuditLog.objects.filter(action__in=actions)
    assert {log.action for log in logs} == actions
    for log in logs:
        assert set(log.after) == {"property_id", "verification_id", "kind", "status"}
        rendered = repr(log.before) + repr(log.after)
        assert PRIVATE_FIELD_EVIDENCE not in rendered
        assert PRIVATE_REASON not in rendered
