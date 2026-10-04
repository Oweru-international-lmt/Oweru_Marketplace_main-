from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from rest_framework.test import APIClient

from apps.localities.models import District, Locality, Region, Ward
from apps.properties.models import PropertyRecord
from apps.properties.services import create_property_record
from apps.roles.catalog import (
    ROLE_AGENT,
    ROLE_BUYER,
    ROLE_LOCAL_OFFICIAL,
    ROLE_MANAGEMENT,
    ROLE_MARKETER,
    ROLE_OWNER,
    ROLE_PROFESSIONAL,
    ROLE_VERIFIER,
)
from apps.roles.models import Role, UserRole
from apps.roles.services import bootstrap_canonical_roles


pytestmark = pytest.mark.django_db


def create_user(email, *, is_active=True):
    return get_user_model().objects.create_user(
        email=email,
        phone=f"+255{abs(hash(email)) % 1000000000:09d}",
        full_name="Property API User",
        password="StrongPass123!",
        is_active=is_active,
    )


def grant_role(user, role_code):
    bootstrap_canonical_roles()
    role = Role.objects.get(code=role_code)
    return UserRole.objects.create(user=user, role=role, assigned_by=user)


def user_with_role(email, role_code, *, is_active=True):
    user = create_user(email, is_active=is_active)
    grant_role(user, role_code)
    return user


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def create_hierarchy(prefix="API", *, approved=True):
    region = Region.objects.create(name=f"{prefix} Region")
    district = District.objects.create(region=region, name=f"{prefix} District")
    ward = Ward.objects.create(district=district, name=f"{prefix} Ward")
    locality = Locality.objects.create(
        ward=ward,
        name=f"{prefix} Street",
        kind=Locality.Kind.STREET,
        approved=approved,
    )
    return region, district, ward, locality


def point_payload(longitude=39.2083, latitude=-6.7924):
    return {"type": "Point", "coordinates": [longitude, latitude]}


def polygon_payload():
    return {
        "type": "Polygon",
        "coordinates": [
            [[39.20, -6.79], [39.21, -6.79], [39.21, -6.80], [39.20, -6.80], [39.20, -6.79]]
        ],
    }


def payload(prefix="API", *, approved=True, **overrides):
    region, district, ward, locality = create_hierarchy(prefix, approved=approved)
    data = {
        "category": PropertyRecord.Category.LAND,
        "pin": point_payload(),
        "boundary": None,
        "region": str(region.pk),
        "district": str(district.pk),
        "ward": str(ward.pk),
        "locality": str(locality.pk),
        "stated_size": "1200.50",
        "size_unit": "sqm",
        "title_type": PropertyRecord.TitleType.UNKNOWN,
    }
    data.update(overrides)
    return data


def typed_payload(prefix="TypedAPI", *, name="Typed Street", kind=Locality.Kind.STREET, **overrides):
    data = payload(prefix)
    data.pop("locality")
    data["locality_name"] = name
    data["locality_kind"] = kind
    data.update(overrides)
    return data


def create_record(actor, prefix="Record", **overrides):
    region, district, ward, locality = create_hierarchy(prefix)
    attrs = {
        "category": PropertyRecord.Category.LAND,
        "pin": Point(39.2083, -6.7924, srid=4326),
        "boundary": None,
        "region": region,
        "district": district,
        "ward": ward,
        "locality": locality,
        "stated_size": Decimal("1200.50"),
        "size_unit": "sqm",
        "title_type": PropertyRecord.TitleType.UNKNOWN,
    }
    attrs.update(overrides)
    return create_property_record(actor=actor, **attrs)


def create_record_direct(creator, prefix="Direct", **overrides):
    region, district, ward, locality = create_hierarchy(prefix)
    attrs = {
        "property_id": f"TEST-{prefix.upper()}",
        "category": PropertyRecord.Category.LAND,
        "pin": Point(39.2083, -6.7924, srid=4326),
        "boundary": None,
        "region": region,
        "district": district,
        "ward": ward,
        "locality": locality,
        "stated_size": Decimal("1200.50"),
        "size_unit": "sqm",
        "title_type": PropertyRecord.TitleType.UNKNOWN,
        "created_by": creator,
    }
    attrs.update(overrides)
    return PropertyRecord.objects.create(**attrs)


def test_property_api_requires_authentication():
    owner = user_with_role("auth-owner@example.test", ROLE_OWNER)
    record = create_record(owner, "AuthRequired")

    assert APIClient().get("/api/v1/properties/").status_code == 401
    assert APIClient().post("/api/v1/properties/", payload("AnonCreate"), format="json").status_code == 401
    assert APIClient().get(f"/api/v1/properties/{record.property_id}/").status_code == 401
    assert (
        APIClient()
        .patch(f"/api/v1/properties/{record.property_id}/", {"category": PropertyRecord.Category.HOUSE}, format="json")
        .status_code
        == 401
    )


@pytest.mark.parametrize("role_code", [ROLE_OWNER, ROLE_AGENT])
def test_owner_or_agent_can_create_property(role_code):
    actor = user_with_role(f"create-{role_code}@example.test", role_code)

    response = client_for(actor).post("/api/v1/properties/", payload(f"Create{role_code}"), format="json")

    assert response.status_code == 201
    assert response.data["property_id"].startswith("OWR-")
    assert "created_by" not in response.data
    assert PropertyRecord.objects.get(property_id=response.data["property_id"]).created_by == actor


@pytest.mark.parametrize(
    "role_code",
    [ROLE_BUYER, ROLE_MANAGEMENT, ROLE_VERIFIER, ROLE_MARKETER, ROLE_PROFESSIONAL, ROLE_LOCAL_OFFICIAL],
)
def test_non_lister_roles_cannot_create_property(role_code):
    actor = user_with_role(f"deny-create-{role_code}@example.test", role_code)

    response = client_for(actor).post("/api/v1/properties/", payload(f"Deny{role_code}"), format="json")

    assert response.status_code == 403
    assert not PropertyRecord.objects.exists()


def test_inactive_user_list_exposes_no_records_and_create_is_denied():
    inactive = user_with_role("inactive-api@example.test", ROLE_OWNER, is_active=False)

    assert client_for(inactive).get("/api/v1/properties/").data == []
    assert client_for(inactive).post("/api/v1/properties/", payload("InactiveCreate"), format="json").status_code == 403


def test_list_visibility_is_private_to_creator_or_management():
    owner = user_with_role("list-owner@example.test", ROLE_OWNER)
    agent = user_with_role("list-agent@example.test", ROLE_AGENT)
    buyer = user_with_role("list-buyer@example.test", ROLE_BUYER)
    management = user_with_role("list-management@example.test", ROLE_MANAGEMENT)
    owner_record = create_record(owner, "ListOwner")
    agent_record = create_record(agent, "ListAgent")
    buyer_record = create_record_direct(buyer, "ListBuyerHistorical")

    owner_ids = {item["property_id"] for item in client_for(owner).get("/api/v1/properties/").data}
    buyer_ids = {item["property_id"] for item in client_for(buyer).get("/api/v1/properties/").data}
    management_ids = {item["property_id"] for item in client_for(management).get("/api/v1/properties/").data}

    assert owner_ids == {owner_record.property_id}
    assert buyer_ids == {buyer_record.property_id}
    assert management_ids == {owner_record.property_id, agent_record.property_id, buyer_record.property_id}


def test_detail_access_creator_management_unknown_and_unrelated_users():
    creator = user_with_role("detail-creator@example.test", ROLE_OWNER)
    unrelated = user_with_role("detail-agent@example.test", ROLE_AGENT)
    management = user_with_role("detail-management@example.test", ROLE_MANAGEMENT)
    record = create_record(creator, "Detail")

    creator_response = client_for(creator).get(f"/api/v1/properties/{record.property_id}/")
    unrelated_response = client_for(unrelated).get(f"/api/v1/properties/{record.property_id}/")
    management_response = client_for(management).get(f"/api/v1/properties/{record.property_id}/")
    unknown_response = client_for(creator).get("/api/v1/properties/OWR-DOESNOTEXIST/")

    assert creator_response.status_code == 200
    assert creator_response.data["pin"] == point_payload()
    assert unrelated_response.status_code == 403
    assert management_response.status_code == 200
    assert unknown_response.status_code == 404


def test_patch_creator_management_and_unrelated_authorization():
    creator = user_with_role("patch-creator@example.test", ROLE_OWNER)
    management = user_with_role("patch-management@example.test", ROLE_MANAGEMENT)
    unrelated = user_with_role("patch-unrelated@example.test", ROLE_AGENT)
    record = create_record(creator, "Patch")

    response = client_for(creator).patch(
        f"/api/v1/properties/{record.property_id}/",
        {"category": PropertyRecord.Category.HOUSE},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["category"] == PropertyRecord.Category.HOUSE

    response = client_for(management).patch(
        f"/api/v1/properties/{record.property_id}/",
        {"title_type": PropertyRecord.TitleType.CCRO},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["title_type"] == PropertyRecord.TitleType.CCRO

    response = client_for(unrelated).patch(
        f"/api/v1/properties/{record.property_id}/",
        {"category": PropertyRecord.Category.COMMERCIAL},
        format="json",
    )
    assert response.status_code == 403


def test_patch_partial_update_and_invalid_hierarchy_rollback():
    creator = user_with_role("patch-hierarchy@example.test", ROLE_OWNER)
    record = create_record(creator, "PatchHierarchy")
    original_locality_id = record.locality_id
    _, _, _, other_locality = create_hierarchy("OtherPatchHierarchy")

    response = client_for(creator).patch(
        f"/api/v1/properties/{record.property_id}/",
        {"stated_size": "999.25"},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["stated_size"] == "999.25"

    response = client_for(creator).patch(
        f"/api/v1/properties/{record.property_id}/",
        {"locality": str(other_locality.pk)},
        format="json",
    )
    assert response.status_code == 400
    record.refresh_from_db()
    assert record.locality_id == original_locality_id


def test_create_with_approved_or_pending_existing_locality():
    actor = user_with_role("existing-locality-api@example.test", ROLE_OWNER)

    approved_response = client_for(actor).post("/api/v1/properties/", payload("ExistingApproved"), format="json")
    pending_response = client_for(actor).post(
        "/api/v1/properties/",
        payload("ExistingPending", approved=False),
        format="json",
    )

    assert approved_response.status_code == 201
    assert approved_response.data["locality"]["approved"] is True
    assert pending_response.status_code == 201
    assert pending_response.data["locality"]["approved"] is False


@pytest.mark.parametrize("kind", [Locality.Kind.STREET, Locality.Kind.VILLAGE])
def test_create_with_typed_locality_creates_pending(kind):
    actor = user_with_role(f"typed-{kind}@example.test", ROLE_OWNER)

    response = client_for(actor).post(
        "/api/v1/properties/",
        typed_payload(f"Typed{kind}", name=f"New {kind}", kind=kind),
        format="json",
    )

    assert response.status_code == 201
    locality = Locality.objects.get(pk=response.data["locality"]["id"])
    assert locality.name == f"New {kind}"
    assert locality.kind == kind
    assert locality.approved is False


def test_typed_locality_reuses_case_insensitive_approved_or_pending_match():
    actor = user_with_role("typed-reuse-api@example.test", ROLE_OWNER)
    approved_data = payload("ReuseApproved")
    approved_locality = Locality.objects.get(pk=approved_data["locality"])
    pending_data = payload("ReusePending", approved=False)
    pending_locality = Locality.objects.get(pk=pending_data["locality"])

    approved_data.pop("locality")
    approved_data["locality_name"] = approved_locality.name.upper()
    approved_data["locality_kind"] = approved_locality.kind
    pending_data.pop("locality")
    pending_data["locality_name"] = pending_locality.name.upper()
    pending_data["locality_kind"] = pending_locality.kind

    approved_response = client_for(actor).post("/api/v1/properties/", approved_data, format="json")
    pending_response = client_for(actor).post("/api/v1/properties/", pending_data, format="json")

    assert approved_response.status_code == 201
    assert approved_response.data["locality"]["id"] == str(approved_locality.pk)
    assert pending_response.status_code == 201
    assert pending_response.data["locality"]["id"] == str(pending_locality.pk)
    assert Locality.objects.filter(name__icontains="Reuse").count() == 2


def test_ambiguous_or_unauthorized_typed_locality_creates_no_side_effects():
    owner = user_with_role("ambiguous-owner-api@example.test", ROLE_OWNER)
    buyer = user_with_role("typed-buyer-api@example.test", ROLE_BUYER)
    before_localities = Locality.objects.count()
    ambiguous = typed_payload("AmbiguousAPI", name="Ambiguous Street")
    ambiguous["locality"] = payload("AmbiguousExisting")["locality"]

    ambiguous_response = client_for(owner).post("/api/v1/properties/", ambiguous, format="json")
    unauthorized_response = client_for(buyer).post(
        "/api/v1/properties/",
        typed_payload("UnauthorizedTyped", name="Unauthorized Street"),
        format="json",
    )

    assert ambiguous_response.status_code == 400
    assert unauthorized_response.status_code == 403
    assert not Locality.objects.filter(name__iexact="Unauthorized Street").exists()
    assert PropertyRecord.objects.count() == 0
    assert Locality.objects.count() >= before_localities


def test_patch_switches_to_existing_or_typed_locality():
    creator = user_with_role("patch-locality-api@example.test", ROLE_OWNER)
    record = create_record(creator, "PatchLocalityOriginal")
    region, district, ward, locality = create_hierarchy("PatchLocalityExisting")

    existing_response = client_for(creator).patch(
        f"/api/v1/properties/{record.property_id}/",
        {"region": str(region.pk), "district": str(district.pk), "ward": str(ward.pk), "locality": str(locality.pk)},
        format="json",
    )
    assert existing_response.status_code == 200
    assert existing_response.data["locality"]["id"] == str(locality.pk)

    typed_response = client_for(creator).patch(
        f"/api/v1/properties/{record.property_id}/",
        {"locality_name": "Patch Typed Village", "locality_kind": Locality.Kind.VILLAGE},
        format="json",
    )
    assert typed_response.status_code == 200
    assert typed_response.data["locality"]["name"] == "Patch Typed Village"
    assert typed_response.data["locality"]["approved"] is False


def test_valid_geometry_serialization_and_null_boundary():
    actor = user_with_role("geometry-valid-api@example.test", ROLE_OWNER)
    data = payload("GeometryValid", boundary=polygon_payload())

    response = client_for(actor).post("/api/v1/properties/", data, format="json")

    assert response.status_code == 201
    assert response.data["pin"] == point_payload()
    assert response.data["boundary"] == polygon_payload()
    record = PropertyRecord.objects.get(property_id=response.data["property_id"])
    assert record.pin.srid == 4326
    assert record.boundary.srid == 4326

    null_response = client_for(actor).post("/api/v1/properties/", payload("GeometryNull"), format="json")
    assert null_response.status_code == 201
    assert null_response.data["boundary"] is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("pin", polygon_payload()),
        ("boundary", point_payload()),
        ("pin", {"type": "Point", "coordinates": [181, -6.7]}),
        ("pin", {"type": "Point", "coordinates": [39.2, -91]}),
        ("pin", {"type": "Point", "coordinates": ["east", -6.7]}),
        ("boundary", {"type": "Polygon", "coordinates": [[[39.2, -6.7], [39.3, -6.7], [39.2, -6.7]]]}),
    ],
)
def test_invalid_geometry_rejected(field, value):
    actor = user_with_role(f"geometry-invalid-{abs(hash((field, str(value))))}@example.test", ROLE_OWNER)
    data = payload(f"GeometryInvalid{abs(hash(str(value))) % 10000}")
    data[field] = value

    response = client_for(actor).post("/api/v1/properties/", data, format="json")

    assert response.status_code == 400
    assert not PropertyRecord.objects.exists()


def test_mass_assignment_payloads_are_rejected_and_do_not_mutate_identity_fields():
    actor = user_with_role("mass-api@example.test", ROLE_OWNER)
    other = user_with_role("mass-other-api@example.test", ROLE_OWNER)
    record = create_record(actor, "MassAssignment")
    original_property_id = record.property_id
    original_created_by_id = record.created_by_id

    hostile_fields = (
        "property_id",
        "created_by",
        "owner",
        "owner_id",
        "agent",
        "lister",
        "lister_kind",
        "verification_level",
        "status",
        "price",
        "owner_price",
        "selling_price",
        "published_at",
        "is_promoted",
    )
    for field in hostile_fields:
        post_payload = payload(f"Mass{field}", **{field: str(other.pk)})
        post_response = client_for(actor).post("/api/v1/properties/", post_payload, format="json")
        assert post_response.status_code == 400

        patch_response = client_for(actor).patch(
            f"/api/v1/properties/{record.property_id}/",
            {field: str(other.pk)},
            format="json",
        )
        assert patch_response.status_code == 400

    record.refresh_from_db()
    assert record.property_id == original_property_id
    assert record.created_by_id == original_created_by_id


def test_put_and_delete_are_not_supported():
    actor = user_with_role("methods-api@example.test", ROLE_OWNER)
    record = create_record(actor, "Methods")
    client = client_for(actor)

    assert client.put(f"/api/v1/properties/{record.property_id}/", {}, format="json").status_code == 405
    assert client.delete(f"/api/v1/properties/{record.property_id}/").status_code == 405
