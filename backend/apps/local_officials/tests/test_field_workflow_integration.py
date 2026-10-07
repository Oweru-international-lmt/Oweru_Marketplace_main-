from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.local_officials.services import revoke_jurisdiction, update_local_official_profile
from apps.roles.catalog import ROLE_LOCAL_OFFICIAL
from apps.roles.models import UserRole
from apps.verification.audit_events import (
    VERIFICATION_FIELD_APPROVED,
    VERIFICATION_FIELD_REJECTED,
)
from apps.verification.models import PropertyVerification
from apps.verification.services import (
    expire_field_verifications,
    get_effective_verification_level,
)

from .test_field_verification_authorization import api_client, official_with_assignment
from apps.verification.tests.test_field_lifecycle import submitted_field


pytestmark = pytest.mark.django_db


def canonical_field_url(verification=None, suffix=""):
    base = "/api/v1/local-official/verifications/field/"
    if verification is None:
        return base
    return f"{base}{verification.pk}/{suffix}"


def test_level_two_submission_requires_no_local_official_and_covered_officials_share_one_pending_case():
    owner, property_record, _, field = submitted_field()
    assert field.status == PropertyVerification.Status.PENDING
    assert get_effective_verification_level(user=owner, property_record=property_record) == 2

    ward_official, _, _, _ = official_with_assignment(property_record)
    region_official, _, _, _ = official_with_assignment(
        property_record,
        scope="REGION",
    )

    assert api_client(ward_official).get(canonical_field_url()).data["count"] == 1
    assert api_client(region_official).get(canonical_field_url()).data["count"] == 1

    approved = api_client(ward_official).post(canonical_field_url(field, "approve/"), {}, format="json")
    assert approved.status_code == 200
    field.refresh_from_db()
    assert field.status == PropertyVerification.Status.APPROVED
    assert field.reviewed_by_id == ward_official.pk
    assert get_effective_verification_level(user=owner, property_record=property_record) == 3
    assert AuditLog.objects.filter(
        action=VERIFICATION_FIELD_APPROVED,
        entity_id=str(field.pk),
    ).count() == 1

    second_review = api_client(region_official).post(
        canonical_field_url(field, "reject/"),
        {"reason": "Already reviewed"},
        format="json",
    )
    assert second_review.status_code == 400
    assert AuditLog.objects.filter(
        action=VERIFICATION_FIELD_APPROVED,
        entity_id=str(field.pk),
    ).count() == 1


def test_canonical_rejection_is_terminal_and_does_not_contribute_to_level_three():
    owner, property_record, _, field = submitted_field()
    reviewer, _, _, _ = official_with_assignment(property_record)

    rejected = api_client(reviewer).post(
        canonical_field_url(field, "reject/"),
        {"reason": "Field report is insufficient"},
        format="json",
    )
    assert rejected.status_code == 200
    field.refresh_from_db()
    assert field.status == PropertyVerification.Status.REJECTED
    assert field.reviewed_by_id == reviewer.pk
    assert field.reviewed_at is not None
    assert get_effective_verification_level(user=owner, property_record=property_record) == 2
    assert AuditLog.objects.filter(
        action=VERIFICATION_FIELD_REJECTED,
        entity_id=str(field.pk),
    ).count() == 1


def test_authority_loss_after_approval_does_not_rewrite_history_or_level_three():
    owner, property_record, _, field = submitted_field()
    reviewer, manager, profile, assignment = official_with_assignment(property_record)
    assert api_client(reviewer).post(canonical_field_url(field, "approve/"), {}, format="json").status_code == 200

    revoke_jurisdiction(actor=manager, assignment=assignment)
    update_local_official_profile(actor=manager, profile=profile, is_active=False)
    role_assignment = UserRole.objects.get(user=reviewer, role__code=ROLE_LOCAL_OFFICIAL)
    role_assignment.is_active = False
    role_assignment.save(update_fields=["is_active"])

    field.refresh_from_db()
    assert field.status == PropertyVerification.Status.APPROVED
    assert field.reviewed_by_id == reviewer.pk
    assert get_effective_verification_level(user=owner, property_record=property_record) == 3
    assert api_client(reviewer).get(canonical_field_url(field)).status_code == 403


def test_expired_assignment_denies_future_review_without_expiring_existing_field_verification():
    owner, property_record, _, field = submitted_field()
    reviewer, _, _, assignment = official_with_assignment(
        property_record,
        expires_at=timezone.now() + timedelta(hours=1),
    )
    assert api_client(reviewer).post(canonical_field_url(field, "approve/"), {}, format="json").status_code == 200
    assignment.expires_at = timezone.now() - timedelta(seconds=1)
    assignment.save(update_fields=["expires_at", "updated_at"])

    field.refresh_from_db()
    assert field.status == PropertyVerification.Status.APPROVED
    assert get_effective_verification_level(user=owner, property_record=property_record) == 3
    assert api_client(reviewer).get(canonical_field_url(field)).status_code == 403

    field.expires_at = timezone.now() - timedelta(seconds=1)
    field.save(update_fields=["expires_at", "updated_at"])
    assert expire_field_verifications() == 1
    assert get_effective_verification_level(user=owner, property_record=property_record) == 2


def test_canonical_actions_reject_mass_assignment_and_stale_jurisdiction_without_success_audits():
    _, property_record, _, field = submitted_field()
    reviewer, manager, _, assignment = official_with_assignment(property_record)
    protected_payload = {
        "status": "APPROVED",
        "kind": "DOCUMENT",
        "property": "OWR-ATTACK",
        "reviewed_by": "attacker",
        "reviewed_at": "2030-01-01T00:00:00Z",
        "expires_at": "2030-01-01T00:00:00Z",
        "assignment_id": str(assignment.pk),
        "verification_level": 3,
    }
    rejected = api_client(reviewer).post(canonical_field_url(field, "approve/"), protected_payload, format="json")
    assert rejected.status_code == 400
    field.refresh_from_db()
    assert field.status == PropertyVerification.Status.PENDING

    before = AuditLog.objects.filter(action=VERIFICATION_FIELD_APPROVED).count()
    revoke_jurisdiction(actor=manager, assignment=assignment)
    denied = api_client(reviewer).post(canonical_field_url(field, "approve/"), {}, format="json")
    assert denied.status_code == 403
    field.refresh_from_db()
    assert field.status == PropertyVerification.Status.PENDING
    assert AuditLog.objects.filter(action=VERIFICATION_FIELD_APPROVED).count() == before

