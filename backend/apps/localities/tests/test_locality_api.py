import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.localities.models import District, Locality, Region, Ward
from apps.localities.services import create_pending_locality
from apps.roles.catalog import ROLE_MANAGEMENT
from apps.roles.models import Role, UserRole
from apps.roles.services import bootstrap_canonical_roles


pytestmark = pytest.mark.django_db


def create_user(email):
    return get_user_model().objects.create_user(
        email=email,
        phone=f"+255{abs(hash(email)) % 1000000000:09d}",
        full_name="Synthetic User",
        password="StrongPass123!",
    )


def create_management_user(email="manager-api@example.test"):
    bootstrap_canonical_roles()
    user = create_user(email)
    role = Role.objects.get(code=ROLE_MANAGEMENT)
    UserRole.objects.create(user=user, role=role, assigned_by=user)
    return user


def create_ward():
    region = Region.objects.create(name="Synthetic Region")
    district = District.objects.create(region=region, name="Synthetic District")
    return Ward.objects.create(district=district, name="Synthetic Ward")


def authenticated_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def payload(ward, **extra):
    data = {"ward": str(ward.pk), "name": "Synthetic Street", "kind": Locality.Kind.STREET}
    data.update(extra)
    return data


def test_create_locality_unauthenticated_denied():
    response = APIClient().post("/api/v1/localities/", payload(create_ward()), format="json")

    assert response.status_code == 401


def test_create_locality_non_management_denied():
    response = authenticated_client(create_user("ordinary-api@example.test")).post(
        "/api/v1/localities/",
        payload(create_ward()),
        format="json",
    )

    assert response.status_code == 403


def test_management_creates_approved_locality():
    manager = create_management_user()
    ward = create_ward()

    response = authenticated_client(manager).post("/api/v1/localities/", payload(ward), format="json")

    assert response.status_code == 201
    assert response.data["approved"] is True
    assert response.data["ward"] == ward.pk
    locality = Locality.objects.get()
    assert locality.created_by == manager


def test_client_cannot_control_approved_on_create():
    manager = create_management_user()

    response = authenticated_client(manager).post(
        "/api/v1/localities/",
        payload(create_ward(), approved=False),
        format="json",
    )

    assert response.status_code == 201
    assert response.data["approved"] is True
    assert Locality.objects.get().approved is True


def test_client_cannot_control_created_by_on_create():
    manager = create_management_user()
    other_user = create_user("other-created-by@example.test")

    response = authenticated_client(manager).post(
        "/api/v1/localities/",
        payload(create_ward(), created_by=str(other_user.pk)),
        format="json",
    )

    assert response.status_code == 201
    assert Locality.objects.get().created_by == manager


def test_create_locality_invalid_ward_returns_400():
    manager = create_management_user()

    response = authenticated_client(manager).post(
        "/api/v1/localities/",
        {"ward": "00000000-0000-0000-0000-000000000000", "name": "Synthetic Street", "kind": "street"},
        format="json",
    )

    assert response.status_code == 400


def test_create_locality_invalid_kind_returns_400():
    manager = create_management_user()

    response = authenticated_client(manager).post(
        "/api/v1/localities/",
        {"ward": str(create_ward().pk), "name": "Synthetic Area", "kind": "area"},
        format="json",
    )

    assert response.status_code == 400


def test_create_locality_duplicate_returns_400():
    manager = create_management_user()
    ward = create_ward()
    client = authenticated_client(manager)
    assert client.post("/api/v1/localities/", payload(ward), format="json").status_code == 201

    response = client.post("/api/v1/localities/", payload(ward, name="synthetic street"), format="json")

    assert response.status_code == 400
    assert Locality.objects.count() == 1


def test_approve_locality_unauthenticated_denied():
    user = create_user("pending-api-owner@example.test")
    locality = create_pending_locality(
        actor=user,
        ward=create_ward(),
        name="Synthetic Pending",
        kind=Locality.Kind.STREET,
    )

    response = APIClient().post(f"/api/v1/localities/{locality.pk}/approve/", {}, format="json")

    assert response.status_code == 401


def test_approve_locality_non_management_denied():
    user = create_user("non-manager-approve@example.test")
    locality = create_pending_locality(
        actor=user,
        ward=create_ward(),
        name="Synthetic Pending",
        kind=Locality.Kind.STREET,
    )

    response = authenticated_client(user).post(f"/api/v1/localities/{locality.pk}/approve/", {}, format="json")

    assert response.status_code == 403


def test_management_approves_pending_locality():
    manager = create_management_user()
    user = create_user("pending-owner-api@example.test")
    locality = create_pending_locality(
        actor=user,
        ward=create_ward(),
        name="Synthetic Pending",
        kind=Locality.Kind.STREET,
    )

    response = authenticated_client(manager).post(f"/api/v1/localities/{locality.pk}/approve/", {}, format="json")

    assert response.status_code == 200
    assert response.data["approved"] is True
    locality.refresh_from_db()
    assert locality.approved is True


def test_approve_already_approved_is_idempotent():
    manager = create_management_user()
    response = authenticated_client(manager).post(
        "/api/v1/localities/",
        payload(create_ward()),
        format="json",
    )
    locality_id = response.data["id"]

    response = authenticated_client(manager).post(f"/api/v1/localities/{locality_id}/approve/", {}, format="json")

    assert response.status_code == 200
    assert response.data["approved"] is True
    assert Locality.objects.count() == 1


def test_approve_nonexistent_locality_returns_404():
    manager = create_management_user()

    response = authenticated_client(manager).post(
        "/api/v1/localities/00000000-0000-0000-0000-000000000000/approve/",
        {},
        format="json",
    )

    assert response.status_code == 404


def test_no_pending_creation_endpoint_exists():
    response = authenticated_client(create_user("pending-route@example.test")).post(
        "/api/v1/localities/pending/",
        payload(create_ward()),
        format="json",
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    "url",
    [
        "/api/v1/localities/regions/",
        "/api/v1/localities/districts/",
        "/api/v1/localities/wards/",
    ],
)
def test_no_region_district_ward_mutation_api_exists(url):
    response = authenticated_client(create_management_user(f"{url.split('/')[-2]}@example.test")).post(
        url,
        {},
        format="json",
    )

    assert response.status_code == 405
