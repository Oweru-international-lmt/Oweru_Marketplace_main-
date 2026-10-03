import uuid

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.localities.models import District, Locality, Region, Ward
from apps.localities.services import approve_locality, create_locality, create_pending_locality
from apps.roles.catalog import ROLE_MANAGEMENT
from apps.roles.models import Role, UserRole
from apps.roles.services import bootstrap_canonical_roles, user_has_role


pytestmark = pytest.mark.django_db


def create_user(email):
    return get_user_model().objects.create_user(
        email=email,
        phone=f"+255{abs(hash(email)) % 1000000000:09d}",
        full_name="Synthetic User",
        password="StrongPass123!",
    )


def create_management_user(email="manager@example.test"):
    bootstrap_canonical_roles()
    user = create_user(email)
    role = Role.objects.get(code=ROLE_MANAGEMENT)
    UserRole.objects.create(user=user, role=role, assigned_by=user)
    return user


def create_ward():
    region = Region.objects.create(name="Synthetic Region")
    district = District.objects.create(region=region, name="Synthetic District")
    return Ward.objects.create(district=district, name="Synthetic Ward")


def test_management_creates_street():
    manager = create_management_user()
    ward = create_ward()

    locality = create_locality(actor=manager, ward=ward, name="Synthetic Street", kind=Locality.Kind.STREET)

    assert locality.kind == Locality.Kind.STREET
    assert locality.approved is True
    assert locality.created_by == manager


def test_management_creates_village():
    manager = create_management_user()
    ward = create_ward()

    locality = create_locality(actor=manager, ward=ward, name="Synthetic Village", kind=Locality.Kind.VILLAGE)

    assert locality.kind == Locality.Kind.VILLAGE
    assert locality.approved is True


def test_non_management_cannot_create_locality():
    user = create_user("ordinary@example.test")
    ward = create_ward()

    with pytest.raises(PermissionDenied):
        create_locality(actor=user, ward=ward, name="Synthetic Street", kind=Locality.Kind.STREET)


def test_unauthenticated_actor_cannot_create_locality():
    with pytest.raises(PermissionDenied):
        create_locality(
            actor=AnonymousUser(),
            ward=create_ward(),
            name="Synthetic Street",
            kind=Locality.Kind.STREET,
        )


def test_unpersisted_actor_cannot_create_locality():
    actor = get_user_model()(email="unpersisted@example.test")

    with pytest.raises(PermissionDenied):
        create_locality(actor=actor, ward=create_ward(), name="Synthetic Street", kind=Locality.Kind.STREET)


def test_invalid_kind_rejected_for_management_creation():
    manager = create_management_user()

    with pytest.raises(ValidationError):
        create_locality(actor=manager, ward=create_ward(), name="Synthetic Area", kind="area")


def test_invalid_or_nonexistent_ward_rejected_for_management_creation():
    manager = create_management_user()

    with pytest.raises(ValidationError):
        create_locality(actor=manager, ward=uuid.uuid4(), name="Synthetic Street", kind=Locality.Kind.STREET)


def test_duplicate_locality_rejected_safely():
    manager = create_management_user()
    ward = create_ward()
    create_locality(actor=manager, ward=ward, name="Synthetic Street", kind=Locality.Kind.STREET)

    with pytest.raises(ValidationError):
        create_locality(actor=manager, ward=ward, name="Synthetic Street", kind=Locality.Kind.STREET)

    assert Locality.objects.count() == 1


def test_case_insensitive_duplicate_locality_rejected():
    manager = create_management_user()
    ward = create_ward()
    create_locality(actor=manager, ward=ward, name="Synthetic Street", kind=Locality.Kind.STREET)

    with pytest.raises(ValidationError):
        create_locality(actor=manager, ward=ward, name="synthetic street", kind=Locality.Kind.STREET)


def test_whitespace_normalization_preserved():
    manager = create_management_user()

    locality = create_locality(
        actor=manager,
        ward=create_ward(),
        name="  Synthetic Street  ",
        kind=Locality.Kind.STREET,
    )

    assert locality.name == "Synthetic Street"


def test_authenticated_user_can_create_pending_locality():
    user = create_user("pending@example.test")

    locality = create_pending_locality(
        actor=user,
        ward=create_ward(),
        name="Synthetic Pending",
        kind=Locality.Kind.VILLAGE,
    )

    assert locality.approved is False
    assert locality.created_by == user


def test_pending_creation_does_not_recreate_approved_duplicate():
    manager = create_management_user()
    user = create_user("pending-duplicate@example.test")
    ward = create_ward()
    approved = create_locality(actor=manager, ward=ward, name="Synthetic Street", kind=Locality.Kind.STREET)

    pending = create_pending_locality(actor=user, ward=ward, name="synthetic street", kind=Locality.Kind.STREET)

    assert pending == approved
    assert pending.approved is True
    assert Locality.objects.count() == 1


def test_pending_creation_respects_database_uniqueness():
    user = create_user("pending-unique@example.test")
    ward = create_ward()
    first = create_pending_locality(actor=user, ward=ward, name="Synthetic Pending", kind=Locality.Kind.STREET)

    second = create_pending_locality(actor=user, ward=ward, name="synthetic pending", kind=Locality.Kind.STREET)

    assert second == first
    assert Locality.objects.count() == 1


def test_management_can_approve_pending_locality():
    manager = create_management_user()
    user = create_user("submitter@example.test")
    locality = create_pending_locality(
        actor=user,
        ward=create_ward(),
        name="Synthetic Pending",
        kind=Locality.Kind.STREET,
    )

    approved = approve_locality(locality=locality, approved_by=manager)

    assert approved.approved is True


def test_non_management_cannot_approve_locality():
    user = create_user("approver@example.test")
    locality = create_pending_locality(
        actor=user,
        ward=create_ward(),
        name="Synthetic Pending",
        kind=Locality.Kind.STREET,
    )

    with pytest.raises(PermissionDenied):
        approve_locality(locality=locality, approved_by=user)


def test_unauthenticated_actor_cannot_approve_locality():
    user = create_user("pending-owner@example.test")
    locality = create_pending_locality(
        actor=user,
        ward=create_ward(),
        name="Synthetic Pending",
        kind=Locality.Kind.STREET,
    )

    with pytest.raises(PermissionDenied):
        approve_locality(locality=locality, approved_by=AnonymousUser())


def test_inactive_management_assignment_cannot_approve():
    manager = create_management_user()
    UserRole.objects.filter(user=manager, role__code=ROLE_MANAGEMENT).update(is_active=False)
    user = create_user("inactive-assignment-owner@example.test")
    locality = create_pending_locality(
        actor=user,
        ward=create_ward(),
        name="Synthetic Pending",
        kind=Locality.Kind.STREET,
    )

    with pytest.raises(PermissionDenied):
        approve_locality(locality=locality, approved_by=manager)


def test_inactive_management_role_cannot_approve():
    manager = create_management_user()
    Role.objects.filter(code=ROLE_MANAGEMENT).update(is_active=False)
    user = create_user("inactive-role-owner@example.test")
    locality = create_pending_locality(
        actor=user,
        ward=create_ward(),
        name="Synthetic Pending",
        kind=Locality.Kind.STREET,
    )

    with pytest.raises(PermissionDenied):
        approve_locality(locality=locality, approved_by=manager)


def test_already_approved_locality_approval_is_idempotent():
    manager = create_management_user()
    locality = create_locality(actor=manager, ward=create_ward(), name="Synthetic Street", kind=Locality.Kind.STREET)

    approved = approve_locality(locality=locality, approved_by=manager)

    assert approved.pk == locality.pk
    assert approved.approved is True
    assert Locality.objects.count() == 1


def test_approval_preserves_original_created_by():
    manager = create_management_user()
    user = create_user("submitter-created-by@example.test")
    locality = create_pending_locality(
        actor=user,
        ward=create_ward(),
        name="Synthetic Pending",
        kind=Locality.Kind.STREET,
    )

    approve_locality(locality=locality, approved_by=manager)
    locality.refresh_from_db()

    assert locality.created_by == user
    assert user_has_role(manager, ROLE_MANAGEMENT)
