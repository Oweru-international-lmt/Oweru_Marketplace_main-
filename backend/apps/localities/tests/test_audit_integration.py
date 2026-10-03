import uuid
from unittest.mock import patch

import pytest
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient, APIRequestFactory

from apps.audit.legacy_event_stream.models import AuditEvent
from apps.audit.models import AuditLog
from apps.localities.audit_events import LOCALITY_APPROVED, LOCALITY_CREATED
from apps.localities.models import District, Locality, Region, Ward
from apps.localities.services import (
    approve_locality,
    create_locality,
    create_pending_locality,
    import_reference_localities,
)
from apps.roles.catalog import ROLE_MANAGEMENT
from apps.roles.models import Role, UserRole
from apps.roles.services import bootstrap_canonical_roles
from django.contrib.auth import get_user_model


pytestmark = pytest.mark.django_db


def create_user(email):
    return get_user_model().objects.create_user(
        email=email,
        phone=f"+255{abs(hash(email)) % 1000000000:09d}",
        full_name="Synthetic User",
        password="StrongPass123!",
    )


def create_management_user(email="audit-manager@example.test"):
    bootstrap_canonical_roles()
    user = create_user(email)
    role = Role.objects.get(code=ROLE_MANAGEMENT)
    UserRole.objects.create(user=user, role=role, assigned_by=user)
    return user


def create_ward():
    region = Region.objects.create(name="Synthetic Region")
    district = District.objects.create(region=region, name="Synthetic District")
    return Ward.objects.create(district=district, name="Synthetic Ward")


def audit_request(actor):
    request = APIRequestFactory().post("/internal/", REMOTE_ADDR="203.0.113.50", HTTP_USER_AGENT="LocalityAudit/1.0")
    request.user = actor
    return request


def test_successful_management_create_produces_locality_created_audit():
    manager = create_management_user()
    ward = create_ward()

    locality = create_locality(
        actor=manager,
        ward=ward,
        name="Synthetic Street",
        kind=Locality.Kind.STREET,
        request=audit_request(manager),
    )
    log = AuditLog.objects.get(action=LOCALITY_CREATED)

    assert log.actor == manager
    assert log.entity_type == "Locality"
    assert log.entity_id == str(locality.pk)
    assert log.before == {}
    assert log.after == {
        "locality_id": str(locality.pk),
        "name": "Synthetic Street",
        "kind": "street",
        "ward_id": str(ward.pk),
        "approved": True,
    }
    assert log.ip_address == "203.0.113.50"
    assert log.user_agent == "LocalityAudit/1.0"


def test_unauthorized_creation_creates_no_success_audit():
    user = create_user("ordinary-locality-audit@example.test")

    with pytest.raises(PermissionDenied):
        create_locality(actor=user, ward=create_ward(), name="Synthetic Street", kind=Locality.Kind.STREET)

    assert not AuditLog.objects.filter(action=LOCALITY_CREATED).exists()


def test_duplicate_or_failed_creation_creates_no_extra_success_audit():
    manager = create_management_user()
    ward = create_ward()
    create_locality(actor=manager, ward=ward, name="Synthetic Street", kind=Locality.Kind.STREET)
    before_count = AuditLog.objects.filter(action=LOCALITY_CREATED).count()

    with pytest.raises(ValidationError):
        create_locality(actor=manager, ward=ward, name="synthetic street", kind=Locality.Kind.STREET)
    with pytest.raises(ValidationError):
        create_locality(actor=manager, ward=uuid.uuid4(), name="Broken Street", kind=Locality.Kind.STREET)

    assert AuditLog.objects.filter(action=LOCALITY_CREATED).count() == before_count


def test_create_audit_failure_rolls_back_locality_creation():
    manager = create_management_user()

    with patch("apps.localities.services.create_audit_log", side_effect=RuntimeError("audit failed")), pytest.raises(
        RuntimeError
    ):
        create_locality(actor=manager, ward=create_ward(), name="Rollback Street", kind=Locality.Kind.STREET)

    assert not Locality.objects.filter(name="Rollback Street").exists()
    assert not AuditLog.objects.filter(action=LOCALITY_CREATED).exists()


def test_successful_pending_approval_produces_locality_approved_audit():
    manager = create_management_user()
    submitter = create_user("locality-submitter@example.test")
    ward = create_ward()
    locality = create_pending_locality(
        actor=submitter,
        ward=ward,
        name="Synthetic Pending",
        kind=Locality.Kind.VILLAGE,
    )

    approved = approve_locality(locality=locality, approved_by=manager, request=audit_request(manager))
    log = AuditLog.objects.get(action=LOCALITY_APPROVED)

    assert approved.approved is True
    assert approved.created_by == submitter
    assert log.actor == manager
    assert log.entity_type == "Locality"
    assert log.entity_id == str(locality.pk)
    assert log.before == {
        "locality_id": str(locality.pk),
        "name": "Synthetic Pending",
        "kind": "village",
        "ward_id": str(ward.pk),
        "approved": False,
    }
    assert log.after == {
        "locality_id": str(locality.pk),
        "name": "Synthetic Pending",
        "kind": "village",
        "ward_id": str(ward.pk),
        "approved": True,
    }


def test_already_approved_approval_creates_no_duplicate_approved_audit():
    manager = create_management_user()
    locality = create_locality(actor=manager, ward=create_ward(), name="Synthetic Street", kind=Locality.Kind.STREET)

    approve_locality(locality=locality, approved_by=manager)

    assert not AuditLog.objects.filter(action=LOCALITY_APPROVED).exists()


def test_unauthorized_or_failed_approval_creates_no_success_audit():
    manager = create_management_user()
    ordinary = create_user("ordinary-approval-audit@example.test")
    submitter = create_user("pending-audit-owner@example.test")
    locality = create_pending_locality(
        actor=submitter,
        ward=create_ward(),
        name="Synthetic Pending",
        kind=Locality.Kind.STREET,
    )

    with pytest.raises(PermissionDenied):
        approve_locality(locality=locality, approved_by=ordinary)
    with pytest.raises(ValidationError):
        approve_locality(locality=uuid.uuid4(), approved_by=manager)

    assert not AuditLog.objects.filter(action=LOCALITY_APPROVED).exists()
    locality.refresh_from_db()
    assert locality.approved is False


def test_approval_audit_failure_rolls_back_state_change():
    manager = create_management_user()
    submitter = create_user("rollback-pending-owner@example.test")
    locality = create_pending_locality(
        actor=submitter,
        ward=create_ward(),
        name="Rollback Pending",
        kind=Locality.Kind.STREET,
    )

    with patch("apps.localities.services.create_audit_log", side_effect=RuntimeError("audit failed")), pytest.raises(
        RuntimeError
    ):
        approve_locality(locality=locality, approved_by=manager)

    locality.refresh_from_db()
    assert locality.approved is False
    assert not AuditLog.objects.filter(action=LOCALITY_APPROVED).exists()


def test_locality_audit_metadata_contains_no_sensitive_secrets():
    manager = create_management_user()
    submitter = create_user("secret-pending-owner@example.test")
    locality = create_pending_locality(
        actor=submitter,
        ward=create_ward(),
        name="Secret Safe Pending",
        kind=Locality.Kind.STREET,
    )
    create_locality(actor=manager, ward=locality.ward, name="Secret Safe Street", kind=Locality.Kind.VILLAGE)
    approve_locality(locality=locality, approved_by=manager)

    metadata = " ".join(
        str(value)
        for log in AuditLog.objects.filter(action__in=[LOCALITY_CREATED, LOCALITY_APPROVED])
        for value in [log.before, log.after]
    )
    assert "StrongPass123!" not in metadata
    assert "password" not in metadata.lower()
    assert "token" not in metadata.lower()
    assert "jwt" not in metadata.lower()
    assert "authorization" not in metadata.lower()


def test_pending_creation_import_and_public_reads_do_not_emit_locality_audit_events():
    user = create_user("boundary-locality@example.test")
    ward = create_ward()
    create_pending_locality(actor=user, ward=ward, name="Pending Boundary", kind=Locality.Kind.STREET)
    import_reference_localities(
        [
            {
                "name": "Imported Synthetic Region",
                "districts": [
                    {"name": "Imported Synthetic District", "wards": [{"name": "Imported Synthetic Ward"}]},
                ],
            }
        ]
    )
    Locality.objects.create(ward=ward, name="Approved Boundary", kind=Locality.Kind.VILLAGE, approved=True)

    response = APIClient().get("/api/v1/localities/?search=boundary")

    assert response.status_code == 200
    assert not AuditLog.objects.filter(action__in=[LOCALITY_CREATED, LOCALITY_APPROVED]).exists()


def test_canonical_locality_mutations_create_no_legacy_audit_event():
    manager = create_management_user()
    submitter = create_user("legacy-boundary-owner@example.test")
    locality = create_pending_locality(
        actor=submitter,
        ward=create_ward(),
        name="Legacy Boundary",
        kind=Locality.Kind.STREET,
    )
    before_legacy_count = AuditEvent.objects.count()

    create_locality(actor=manager, ward=locality.ward, name="Legacy Boundary Village", kind=Locality.Kind.VILLAGE)
    approve_locality(locality=locality, approved_by=manager)

    assert AuditLog.objects.filter(action__in=[LOCALITY_CREATED, LOCALITY_APPROVED]).count() == 2
    assert AuditEvent.objects.count() == before_legacy_count
