import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.localities.models import District, Locality, Region, Ward
from apps.roles.catalog import ROLE_MANAGEMENT
from apps.roles.models import Role, UserRole
from apps.roles.services import bootstrap_canonical_roles


pytestmark = pytest.mark.django_db


def items(response):
    return response.data["results"] if isinstance(response.data, dict) and "results" in response.data else response.data


def names(response):
    return [item["name"] for item in items(response)]


def create_user(email):
    return get_user_model().objects.create_user(
        email=email,
        phone=f"+255{abs(hash(email)) % 1000000000:09d}",
        full_name="Synthetic User",
        password="StrongPass123!",
    )


def create_management_user(email="read-manager@example.test"):
    bootstrap_canonical_roles()
    user = create_user(email)
    role = Role.objects.get(code=ROLE_MANAGEMENT)
    UserRole.objects.create(user=user, role=role, assigned_by=user)
    return user


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def graph():
    region_a = Region.objects.create(name="Alpha Region")
    region_b = Region.objects.create(name="Beta Region")
    district_a1 = District.objects.create(region=region_a, name="Alpha Central")
    district_a2 = District.objects.create(region=region_a, name="Alpha Coast")
    district_b1 = District.objects.create(region=region_b, name="Beta Central")
    ward_a11 = Ward.objects.create(district=district_a1, name="Alpha Ward One")
    ward_a12 = Ward.objects.create(district=district_a1, name="Alpha Ward Two")
    ward_a21 = Ward.objects.create(district=district_a2, name="Coast Ward")
    ward_b11 = Ward.objects.create(district=district_b1, name="Beta Ward")
    street = Locality.objects.create(ward=ward_a11, name="Alpha Street", kind=Locality.Kind.STREET, approved=True)
    village = Locality.objects.create(ward=ward_a11, name="Alpha Village", kind=Locality.Kind.VILLAGE, approved=True)
    other = Locality.objects.create(ward=ward_a12, name="Other Street", kind=Locality.Kind.STREET, approved=True)
    pending = Locality.objects.create(ward=ward_a11, name="Pending Street", kind=Locality.Kind.STREET, approved=False)
    return {
        "region_a": region_a,
        "region_b": region_b,
        "district_a1": district_a1,
        "district_a2": district_a2,
        "district_b1": district_b1,
        "ward_a11": ward_a11,
        "ward_a12": ward_a12,
        "ward_a21": ward_a21,
        "ward_b11": ward_b11,
        "street": street,
        "village": village,
        "other": other,
        "pending": pending,
    }


def test_regions_public_list_ordering_and_search():
    Region.objects.create(name="Zulu Region")
    Region.objects.create(name="alpha Region")

    response = APIClient().get("/api/v1/localities/regions/?search=region")

    assert response.status_code == 200
    assert names(response) == ["alpha Region", "Zulu Region"]


def test_region_mutation_methods_not_exposed():
    region = Region.objects.create(name="Alpha Region")

    assert APIClient().post("/api/v1/localities/regions/", {"name": "New"}, format="json").status_code == 405
    assert APIClient().patch(f"/api/v1/localities/regions/{region.pk}/", {"name": "New"}, format="json").status_code == 405
    assert APIClient().delete(f"/api/v1/localities/regions/{region.pk}/").status_code == 405


def test_districts_public_list_region_filter_search_and_isolation():
    data = graph()

    response = APIClient().get(f"/api/v1/localities/districts/?region={data['region_a'].pk}&search=central")

    assert response.status_code == 200
    assert names(response) == ["Alpha Central"]


def test_district_malformed_region_filter_does_not_500():
    response = APIClient().get("/api/v1/localities/districts/?region=not-a-uuid")

    assert response.status_code == 400


def test_wards_public_list_district_filter_search_and_isolation():
    data = graph()

    response = APIClient().get(f"/api/v1/localities/wards/?district={data['district_a1'].pk}&search=ward")

    assert response.status_code == 200
    assert names(response) == ["Alpha Ward One", "Alpha Ward Two"]


def test_ward_malformed_district_filter_does_not_500():
    response = APIClient().get("/api/v1/localities/wards/?district=not-a-uuid")

    assert response.status_code == 400


def test_public_locality_list_returns_only_approved_and_orders_alphabetically():
    graph()
    Locality.objects.create(
        ward=Ward.objects.first(),
        name="Aardvark Street",
        kind=Locality.Kind.STREET,
        approved=True,
    )

    response = APIClient().get("/api/v1/localities/")

    assert response.status_code == 200
    assert names(response) == ["Aardvark Street", "Alpha Street", "Alpha Village", "Other Street"]
    assert "Pending Street" not in names(response)
    assert "approved" not in items(response)[0]


def test_public_locality_ward_filter_does_not_leak_other_wards():
    data = graph()

    response = APIClient().get(f"/api/v1/localities/?ward={data['ward_a11'].pk}")

    assert response.status_code == 200
    assert names(response) == ["Alpha Street", "Alpha Village"]


def test_public_locality_kind_filters():
    graph()

    street_response = APIClient().get("/api/v1/localities/?kind=street")
    village_response = APIClient().get("/api/v1/localities/?kind=village")

    assert street_response.status_code == 200
    assert village_response.status_code == 200
    assert names(street_response) == ["Alpha Street", "Other Street"]
    assert names(village_response) == ["Alpha Village"]


def test_public_locality_search_and_combined_filters():
    data = graph()

    response = APIClient().get(f"/api/v1/localities/?ward={data['ward_a11'].pk}&kind=street&search=alpha")

    assert response.status_code == 200
    assert names(response) == ["Alpha Street"]


def test_public_locality_malformed_filters_do_not_500():
    bad_ward = APIClient().get("/api/v1/localities/?ward=not-a-uuid")
    bad_kind = APIClient().get("/api/v1/localities/?kind=area")

    assert bad_ward.status_code == 400
    assert bad_kind.status_code == 400


def test_public_detail_endpoints():
    data = graph()

    assert APIClient().get(f"/api/v1/localities/regions/{data['region_a'].pk}/").status_code == 200
    assert APIClient().get(f"/api/v1/localities/districts/{data['district_a1'].pk}/").status_code == 200
    assert APIClient().get(f"/api/v1/localities/wards/{data['ward_a11'].pk}/").status_code == 200
    locality_response = APIClient().get(f"/api/v1/localities/{data['street'].pk}/")
    pending_response = APIClient().get(f"/api/v1/localities/{data['pending'].pk}/")

    assert locality_response.status_code == 200
    assert "approved" not in locality_response.data
    assert pending_response.status_code == 404


def test_nonexistent_detail_returns_404():
    response = APIClient().get("/api/v1/localities/00000000-0000-0000-0000-000000000000/")

    assert response.status_code == 404


def test_mutation_security_regression():
    data = graph()
    manager = create_management_user()
    ordinary = create_user("ordinary-read-regression@example.test")

    assert APIClient().get("/api/v1/localities/").status_code == 200
    assert APIClient().post("/api/v1/localities/", {}, format="json").status_code == 401
    assert client_for(ordinary).post("/api/v1/localities/", {}, format="json").status_code == 403
    assert client_for(manager).post(
        "/api/v1/localities/",
        {"ward": str(data["ward_a21"].pk), "name": "Managed Street", "kind": "street"},
        format="json",
    ).status_code == 201
    assert APIClient().post(f"/api/v1/localities/{data['pending'].pk}/approve/", {}, format="json").status_code == 401
    assert client_for(ordinary).post(f"/api/v1/localities/{data['pending'].pk}/approve/", {}, format="json").status_code == 403
