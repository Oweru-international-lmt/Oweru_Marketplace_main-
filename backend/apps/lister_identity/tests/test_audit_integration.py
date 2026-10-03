from datetime import timedelta
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.lister_identity.audit_events import (
    LISTER_IDENTITY_APPROVED,
    LISTER_IDENTITY_CREATED,
    LISTER_IDENTITY_EXPIRED,
    LISTER_IDENTITY_REJECTED,
    LISTER_IDENTITY_SUBMITTED,
    LISTER_IDENTITY_UPDATED,
)
from apps.lister_identity.models import ListerIdentity
from apps.lister_identity.services import (
    approve_lister_identity,
    create_lister_identity,
    expire_lister_identities,
    reject_lister_identity,
    submit_lister_identity,
    update_lister_identity,
)
from apps.roles.catalog import ROLE_BUYER, ROLE_MANAGEMENT, ROLE_OWNER, ROLE_VERIFIER
from apps.roles.models import Role, UserRole
from apps.roles.services import bootstrap_canonical_roles


pytestmark = pytest.mark.django_db

SENSITIVE_NATIONAL_ID = "SENSITIVE-NATIONAL-ID-123"
SENSITIVE_ID_PHOTO = "PRIVATE-ID-PHOTO-SECRET"
SENSITIVE_SELFIE = "PRIVATE-SELFIE-SECRET"
SENSITIVE_MARKERS = [
    SENSITIVE_NATIONAL_ID,
    SENSITIVE_ID_PHOTO,
    SENSITIVE_SELFIE,
    "password",
    "JWT",
    "reset-token-secret",
    "verification-token-secret",
]


def create_user(email=None):
    return get_user_model().objects.create_user(
        email=email or f"audit-{uuid.uuid4().hex[:10]}@example.test",
        phone=f"+255{uuid.uuid4().int % 1000000000:09d}",
        full_name="Audit User",
        password="StrongPass123!",
    )


def grant_role(user, role_code):
    bootstrap_canonical_roles()
    return UserRole.objects.create(user=user, role=Role.objects.get(code=role_code), assigned_by=user)


def owner_user():
    user = create_user()
    grant_role(user, ROLE_OWNER)
    return user


def management_user():
    user = create_user()
    grant_role(user, ROLE_MANAGEMENT)
    return user


def authenticated_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def create_identity(user=None, **overrides):
    data = {
        "national_id_number": SENSITIVE_NATIONAL_ID,
        "national_id_photo_ref": SENSITIVE_ID_PHOTO,
        "live_selfie_ref": SENSITIVE_SELFIE,
    }
    data.update(overrides)
    return create_lister_identity(user=user or owner_user(), **data)


def submitted_identity(user=None):
    user = user or owner_user()
    return submit_lister_identity(user=user, identity=create_identity(user=user))


def approved_identity(*, reviewer=None, expires_at=None):
    identity = approve_lister_identity(identity=submitted_identity(), reviewed_by=reviewer or management_user())
    if expires_at is not None:
        identity.expires_at = expires_at
        identity.save(update_fields=["expires_at", "updated_at"])
    return identity


def latest_action(action):
    return AuditLog.objects.filter(action=action).latest("created_at")


def assert_log_has_no_sensitive_values(log):
    rendered = repr(log.before) + repr(log.after)
    for marker in SENSITIVE_MARKERS:
        assert marker not in rendered


def test_lifecycle_success_events_use_canonical_audit_log_and_safe_metadata():
    owner = owner_user()
    manager = management_user()

    identity = create_identity(user=owner)
    created = latest_action(LISTER_IDENTITY_CREATED)
    assert created.actor == owner
    assert created.entity_type == "ListerIdentity"
    assert created.entity_id == str(identity.pk)
    assert created.after["status"] == ListerIdentity.Status.PENDING
    assert_log_has_no_sensitive_values(created)

    update_lister_identity(user=owner, national_id_number="SENSITIVE-NATIONAL-ID-456")
    updated = latest_action(LISTER_IDENTITY_UPDATED)
    assert updated.actor == owner
    assert updated.entity_id == str(identity.pk)
    assert updated.after == {
        "identity_id": str(identity.pk),
        "national_id_changed": True,
        "id_photo_ref_changed": False,
        "selfie_ref_changed": False,
    }
    assert_log_has_no_sensitive_values(updated)

    submit_lister_identity(user=owner, identity=identity)
    submitted = latest_action(LISTER_IDENTITY_SUBMITTED)
    assert submitted.actor == owner
    assert submitted.after["status"] == ListerIdentity.Status.PENDING
    assert submitted.after["submitted_at"] is not None
    assert_log_has_no_sensitive_values(submitted)

    approve_lister_identity(identity=identity, reviewed_by=manager)
    approved = latest_action(LISTER_IDENTITY_APPROVED)
    assert approved.actor == manager
    assert approved.after["status"] == ListerIdentity.Status.APPROVED
    assert approved.after["reviewed_at"] is not None
    assert approved.after["expires_at"] is not None
    assert_log_has_no_sensitive_values(approved)

    rejected_identity = submitted_identity()
    reject_lister_identity(identity=rejected_identity, reviewed_by=manager, reason="Do not leak this reason")
    rejected = latest_action(LISTER_IDENTITY_REJECTED)
    assert rejected.actor == manager
    assert rejected.after["status"] == ListerIdentity.Status.REJECTED
    assert rejected.after["reason_present"] is True
    assert "Do not leak this reason" not in repr(rejected.after)
    assert_log_has_no_sensitive_values(rejected)

    expiring = approved_identity(reviewer=manager, expires_at=timezone.now() - timedelta(seconds=1))
    assert expire_lister_identities() == 1
    expired = latest_action(LISTER_IDENTITY_EXPIRED)
    assert expired.actor is None
    assert expired.entity_id == str(expiring.pk)
    assert expired.before["status"] == ListerIdentity.Status.APPROVED
    assert expired.after["status"] == ListerIdentity.Status.EXPIRED
    assert_log_has_no_sensitive_values(expired)


def test_no_update_audit_for_no_effective_change():
    owner = owner_user()
    create_identity(user=owner, national_id_number="001")
    before = AuditLog.objects.filter(action=LISTER_IDENTITY_UPDATED).count()

    update_lister_identity(user=owner, national_id_number="001")

    assert AuditLog.objects.filter(action=LISTER_IDENTITY_UPDATED).count() == before


@pytest.mark.parametrize(
    "operation",
    ["create", "update", "submit", "approve", "reject", "expire"],
)
def test_audit_failure_rolls_back_lifecycle_mutations(monkeypatch, operation):
    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    if operation == "create":
        owner = owner_user()
        monkeypatch.setattr("apps.lister_identity.services.create_audit_log", fail_audit)
        with pytest.raises(RuntimeError):
            create_identity(user=owner)
        assert not ListerIdentity.objects.filter(user=owner).exists()
        return

    identity = create_identity()
    monkeypatch.setattr("apps.lister_identity.services.create_audit_log", fail_audit)
    if operation == "update":
        with pytest.raises(RuntimeError):
            update_lister_identity(user=identity.user, national_id_number="999")
        identity.refresh_from_db()
        assert identity.national_id_number == SENSITIVE_NATIONAL_ID
        return

    if operation == "submit":
        with pytest.raises(RuntimeError):
            submit_lister_identity(user=identity.user, identity=identity)
        identity.refresh_from_db()
        assert identity.submitted_at is None
        return

    monkeypatch.setattr("apps.lister_identity.services.create_audit_log", lambda *args, **kwargs: AuditLog.objects.create(action=kwargs["action"], entity_type=kwargs["entity_type"], entity_id=str(kwargs.get("entity_id", ""))))
    identity = submitted_identity()
    manager = management_user()
    monkeypatch.setattr("apps.lister_identity.services.create_audit_log", fail_audit)
    if operation == "approve":
        with pytest.raises(RuntimeError):
            approve_lister_identity(identity=identity, reviewed_by=manager)
        identity.refresh_from_db()
        assert identity.status == ListerIdentity.Status.PENDING
        assert identity.reviewed_at is None
        assert identity.expires_at is None
        return

    if operation == "reject":
        with pytest.raises(RuntimeError):
            reject_lister_identity(identity=identity, reviewed_by=manager, reason="No")
        identity.refresh_from_db()
        assert identity.status == ListerIdentity.Status.PENDING
        assert identity.reviewed_at is None
        assert identity.review_reason == ""
        return

    monkeypatch.setattr("apps.lister_identity.services.create_audit_log", lambda *args, **kwargs: AuditLog.objects.create(action=kwargs["action"], entity_type=kwargs["entity_type"], entity_id=str(kwargs.get("entity_id", ""))))
    approved = approved_identity(expires_at=timezone.now() - timedelta(seconds=1))
    monkeypatch.setattr("apps.lister_identity.services.create_audit_log", fail_audit)
    with pytest.raises(RuntimeError):
        expire_lister_identities()
    approved.refresh_from_db()
    assert approved.status == ListerIdentity.Status.APPROVED


def test_failed_operations_do_not_create_misleading_success_events():
    buyer = create_user()
    grant_role(buyer, ROLE_BUYER)
    with pytest.raises(PermissionDenied):
        create_lister_identity(user=buyer, national_id_number="001")
    assert not AuditLog.objects.filter(action=LISTER_IDENTITY_CREATED).exists()

    owner = owner_user()
    identity = create_lister_identity(user=owner, national_id_number="")
    with pytest.raises(ValidationError):
        submit_lister_identity(user=owner, identity=identity)
    assert not AuditLog.objects.filter(action=LISTER_IDENTITY_SUBMITTED).exists()

    manager = management_user()
    unsubmitted = create_identity()
    with pytest.raises(ValidationError):
        approve_lister_identity(identity=unsubmitted, reviewed_by=manager)
    assert not AuditLog.objects.filter(action=LISTER_IDENTITY_APPROVED).exists()

    own_manager = owner_user()
    grant_role(own_manager, ROLE_MANAGEMENT)
    own_identity = submitted_identity(own_manager)
    with pytest.raises(PermissionDenied):
        approve_lister_identity(identity=own_identity, reviewed_by=own_manager)
    assert not AuditLog.objects.filter(action=LISTER_IDENTITY_APPROVED).exists()

    with pytest.raises(ValidationError):
        reject_lister_identity(identity=submitted_identity(), reviewed_by=manager, reason=" ")
    assert not AuditLog.objects.filter(action=LISTER_IDENTITY_REJECTED).exists()

    already_expired = approved_identity(expires_at=timezone.now() - timedelta(days=1))
    expire_lister_identities()
    assert AuditLog.objects.filter(action=LISTER_IDENTITY_EXPIRED, entity_id=str(already_expired.pk)).count() == 1
    expire_lister_identities()
    assert AuditLog.objects.filter(action=LISTER_IDENTITY_EXPIRED, entity_id=str(already_expired.pk)).count() == 1


def test_management_queue_is_minimized_and_logs_safe_sensitive_access():
    manager = management_user()
    identity = submitted_identity()

    response = authenticated_client(manager).get("/api/v1/management/lister-identities/")

    assert response.status_code == 200
    assert response.data[0]["id"] == str(identity.pk)
    forbidden = {"national_id_number", "national_id_photo_ref", "live_selfie_ref", "review_reason", "email", "phone"}
    assert forbidden.isdisjoint(response.data[0])
    access = AuditLog.objects.get(action="sensitive_data.accessed", entity_id="")
    assert access.actor == manager
    assert access.entity_type == "ListerIdentity"
    assert access.after == {"access_type": "management_review_queue", "purpose": "identity_review"}
    assert_log_has_no_sensitive_values(access)


def test_management_detail_logs_sensitive_access_without_evidence_values_and_unauthorized_does_not():
    identity = submitted_identity()
    manager = management_user()
    verifier = create_user()
    grant_role(verifier, ROLE_VERIFIER)

    denied = authenticated_client(verifier).get(f"/api/v1/management/lister-identities/{identity.pk}/")
    missing = authenticated_client(manager).get("/api/v1/management/lister-identities/00000000-0000-0000-0000-000000000000/")
    assert denied.status_code == 403
    assert missing.status_code == 404
    assert not AuditLog.objects.filter(action="sensitive_data.accessed").exists()

    response = authenticated_client(manager).get(f"/api/v1/management/lister-identities/{identity.pk}/")

    assert response.status_code == 200
    access = AuditLog.objects.get(action="sensitive_data.accessed", entity_id=str(identity.pk))
    assert access.actor == manager
    assert access.entity_type == "ListerIdentity"
    assert access.after == {"access_type": "management_identity_detail", "purpose": "identity_review"}
    assert_log_has_no_sensitive_values(access)


def test_public_and_owner_private_reads_do_not_log_sensitive_access():
    identity = approved_identity()

    public_response = APIClient().get(f"/api/v1/listers/{identity.pk}/")
    private_response = authenticated_client(identity.user).get("/api/v1/lister-identity/me/")

    assert public_response.status_code == 200
    assert private_response.status_code == 200
    assert not AuditLog.objects.filter(action="sensitive_data.accessed").exists()
