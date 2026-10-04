from decimal import Decimal
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from rest_framework.test import APIClient

from apps.listings.models import Listing
from apps.localities.models import District, Locality, Region, Ward
from apps.properties.models import PropertyRecord
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


def create_user(email=None, *, is_active=True):
    email = email or f"listing-api-{uuid.uuid4().hex[:10]}@example.test"
    return get_user_model().objects.create_user(
        email=email,
        phone=f"+2557{abs(hash(email)) % 100000000:08d}",
        full_name="Listing API User",
        password="StrongPass123!",
        is_active=is_active,
    )


def grant_role(user, role_code, *, is_active=True, role_active=True):
    bootstrap_canonical_roles()
    role = Role.objects.get(code=role_code)
    role.is_active = role_active
    role.save(update_fields=["is_active"])
    return UserRole.objects.create(user=user, role=role, is_active=is_active)


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def create_hierarchy(prefix=None):
    prefix = prefix or f"ListingAPI{uuid.uuid4().hex[:8]}"
    region = Region.objects.create(name=f"{prefix} Region")
    district = District.objects.create(region=region, name=f"{prefix} District")
    ward = Ward.objects.create(district=district, name=f"{prefix} Ward")
    locality = Locality.objects.create(
        ward=ward,
        name=f"{prefix} Street",
        kind=Locality.Kind.STREET,
        approved=True,
    )
    return region, district, ward, locality


def create_property_record(*, created_by, prefix=None):
    prefix = prefix or f"ListingProperty{uuid.uuid4().hex[:8]}"
    region, district, ward, locality = create_hierarchy(prefix)
    return PropertyRecord.objects.create(
        property_id=f"OWR-{uuid.uuid4().hex[:16].upper()}",
        category=PropertyRecord.Category.LAND,
        pin=Point(39.2083, -6.7924, srid=4326),
        boundary=None,
        region=region,
        district=district,
        ward=ward,
        locality=locality,
        stated_size=Decimal("1200.50"),
        size_unit="sqm",
        title_type=PropertyRecord.TitleType.UNKNOWN,
        created_by=created_by,
    )


def create_listing_for(actor, *, status=Listing.Status.DRAFT, lister_kind=Listing.ListerKind.OWNER, property_record=None):
    property_record = property_record or create_property_record(created_by=actor)
    selling_price = Decimal("120000000") if lister_kind == Listing.ListerKind.AGENT else Decimal("100000000")
    return Listing.objects.create(
        listing_id=f"LST-{uuid.uuid4().hex[:16].upper()}",
        property=property_record,
        lister=actor,
        lister_kind=lister_kind,
        selling_price=selling_price,
        owner_price=Decimal("100000000"),
        currency=Listing.Currency.TZS,
        status=status,
        description="Private listing",
        features=["road access"],
    )


def create_payload(property_record, *, lister_kind=Listing.ListerKind.OWNER, **overrides):
    data = {
        "property": property_record.property_id,
        "lister_kind": lister_kind,
        "selling_price": "100000000",
        "owner_price": "100000000",
        "description": "Quiet plot near school.",
        "features": ["corner", {"road": True}],
    }
    if lister_kind == Listing.ListerKind.AGENT:
        data["selling_price"] = "120000000"
    data.update(overrides)
    return data


def response_keys(value):
    keys = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            keys.add(key)
            keys.update(response_keys(nested))
    elif isinstance(value, list):
        for item in value:
            keys.update(response_keys(item))
    return keys


def assert_private_listing_response(data):
    assert set(data) == {
        "listing_id",
        "property_id",
        "lister_kind",
        "selling_price",
        "owner_price",
        "currency",
        "status",
        "description",
        "features",
        "created_at",
        "updated_at",
    }
    forbidden_keys = {
        "password",
        "password_hash",
        "email",
        "phone",
        "national_id",
        "national_id_number",
        "national_id_photo_ref",
        "live_selfie_ref",
        "access",
        "refresh",
        "token",
        "secret",
        "owner_whatsapp",
        "owner_bank",
        "pin",
        "boundary",
        "audit",
        "permissions",
        "user_roles",
    }
    assert response_keys(data).isdisjoint(forbidden_keys)


def test_listing_api_requires_authentication():
    owner = create_user("listing-auth-owner@example.test")
    grant_role(owner, ROLE_OWNER)
    listing = create_listing_for(owner)

    assert APIClient().get("/api/v1/listings/").status_code == 401
    assert APIClient().post("/api/v1/listings/", {}, format="json").status_code == 401
    assert APIClient().get(f"/api/v1/listings/{listing.listing_id}/").status_code == 401
    assert APIClient().patch(f"/api/v1/listings/{listing.listing_id}/", {}, format="json").status_code == 401
    assert APIClient().post(f"/api/v1/listings/{listing.listing_id}/activate/", {}, format="json").status_code == 401
    assert APIClient().post(f"/api/v1/listings/{listing.listing_id}/withdraw/", {}, format="json").status_code == 401
    assert APIClient().post(f"/api/v1/management/listings/{listing.listing_id}/suspend/", {}, format="json").status_code == 401
    assert APIClient().post(f"/api/v1/management/listings/{listing.listing_id}/restore/", {}, format="json").status_code == 401


@pytest.mark.parametrize(("role_code", "lister_kind"), [(ROLE_OWNER, Listing.ListerKind.OWNER), (ROLE_AGENT, Listing.ListerKind.AGENT)])
def test_owner_or_agent_can_create_private_draft_listing(role_code, lister_kind):
    actor = create_user(f"listing-create-{role_code}@example.test")
    grant_role(actor, role_code)
    property_record = create_property_record(created_by=actor)

    response = client_for(actor).post("/api/v1/listings/", create_payload(property_record, lister_kind=lister_kind), format="json")

    assert response.status_code == 201
    assert response.data["listing_id"].startswith("LST-")
    assert response.data["property_id"] == property_record.property_id
    assert response.data["status"] == Listing.Status.DRAFT
    assert response.data["currency"] == Listing.Currency.TZS
    assert_private_listing_response(response.data)
    assert Listing.objects.get(listing_id=response.data["listing_id"]).lister == actor


def test_dual_role_user_can_create_either_listing_kind():
    actor = create_user("listing-dual-role@example.test")
    grant_role(actor, ROLE_OWNER)
    grant_role(actor, ROLE_AGENT)
    property_record = create_property_record(created_by=actor)

    owner_response = client_for(actor).post(
        "/api/v1/listings/",
        create_payload(property_record, lister_kind=Listing.ListerKind.OWNER),
        format="json",
    )
    agent_response = client_for(actor).post(
        "/api/v1/listings/",
        create_payload(property_record, lister_kind=Listing.ListerKind.AGENT),
        format="json",
    )

    assert owner_response.status_code == 201
    assert agent_response.status_code == 201


@pytest.mark.parametrize(
    "role_code",
    [ROLE_BUYER, ROLE_MANAGEMENT, ROLE_VERIFIER, ROLE_MARKETER, ROLE_PROFESSIONAL, ROLE_LOCAL_OFFICIAL],
)
def test_non_lister_roles_cannot_create_listing(role_code):
    actor = create_user(f"listing-denied-{role_code}@example.test")
    grant_role(actor, role_code)
    property_record = create_property_record(created_by=actor)

    response = client_for(actor).post("/api/v1/listings/", create_payload(property_record), format="json")

    assert response.status_code == 403


def test_create_denies_unrelated_property_and_price_errors():
    owner = create_user("listing-unrelated-owner@example.test")
    other = create_user("listing-unrelated-other@example.test")
    grant_role(owner, ROLE_OWNER)
    grant_role(other, ROLE_OWNER)
    other_property = create_property_record(created_by=other)

    unrelated_response = client_for(owner).post("/api/v1/listings/", create_payload(other_property), format="json")
    bad_price_response = client_for(owner).post(
        "/api/v1/listings/",
        create_payload(create_property_record(created_by=owner), selling_price="120000000", owner_price="100000000"),
        format="json",
    )

    assert unrelated_response.status_code == 403
    assert bad_price_response.status_code == 400


@pytest.mark.parametrize(
    "field",
    [
        "id",
        "listing_id",
        "lister",
        "status",
        "currency",
        "created_at",
        "updated_at",
        "published_at",
        "verification_level",
        "owner",
        "owner_contact",
        "owner_whatsapp",
        "owner_bank",
        "phone_confirmed",
        "is_verified",
        "promotion",
        "is_promoted",
        "media",
        "photos",
        "documents",
        "audit",
        "created_by",
    ],
)
def test_create_rejects_protected_or_unknown_fields(field):
    actor = create_user(f"listing-create-protected-{field}@example.test")
    grant_role(actor, ROLE_OWNER)
    property_record = create_property_record(created_by=actor)
    data = create_payload(property_record, **{field: "hostile"})

    response = client_for(actor).post("/api/v1/listings/", data, format="json")

    assert response.status_code == 400
    assert field in response.data


def test_private_list_visibility_and_historical_revoked_listing_visibility():
    first = create_user("listing-list-first@example.test")
    second = create_user("listing-list-second@example.test")
    buyer = create_user("listing-list-buyer@example.test")
    manager = create_user("listing-list-manager@example.test")
    grant_role(first, ROLE_OWNER)
    grant_role(second, ROLE_AGENT)
    grant_role(buyer, ROLE_BUYER)
    grant_role(manager, ROLE_MANAGEMENT)
    first_listing = create_listing_for(first)
    second_listing = create_listing_for(second, lister_kind=Listing.ListerKind.AGENT)
    UserRole.objects.filter(user=first, role__code=ROLE_OWNER).update(is_active=False)

    first_ids = {item["listing_id"] for item in client_for(first).get("/api/v1/listings/").data}
    second_ids = {item["listing_id"] for item in client_for(second).get("/api/v1/listings/").data}
    buyer_ids = {item["listing_id"] for item in client_for(buyer).get("/api/v1/listings/").data}
    management_ids = {item["listing_id"] for item in client_for(manager).get("/api/v1/listings/").data}

    assert first_ids == {first_listing.listing_id}
    assert second_ids == {second_listing.listing_id}
    assert buyer_ids == set()
    assert management_ids == {first_listing.listing_id, second_listing.listing_id}


def test_detail_visibility_unknown_listing_and_response_privacy():
    owner = create_user("listing-detail-owner@example.test")
    other = create_user("listing-detail-other@example.test")
    manager = create_user("listing-detail-manager@example.test")
    grant_role(owner, ROLE_OWNER)
    grant_role(other, ROLE_OWNER)
    grant_role(manager, ROLE_MANAGEMENT)
    listing = create_listing_for(owner)

    owner_response = client_for(owner).get(f"/api/v1/listings/{listing.listing_id}/")
    manager_response = client_for(manager).get(f"/api/v1/listings/{listing.listing_id}/")
    other_response = client_for(other).get(f"/api/v1/listings/{listing.listing_id}/")
    unknown_response = client_for(owner).get("/api/v1/listings/LST-DOESNOTEXIST/")

    assert owner_response.status_code == 200
    assert manager_response.status_code == 200
    assert other_response.status_code == 403
    assert unknown_response.status_code == 404
    assert owner_response.data["owner_price"] == "100000000"
    assert_private_listing_response(owner_response.data)
    assert_private_listing_response(manager_response.data)


def test_patch_success_non_draft_management_and_revoked_role_denials():
    owner = create_user("listing-patch-owner@example.test")
    manager = create_user("listing-patch-manager@example.test")
    grant_role(owner, ROLE_OWNER)
    grant_role(manager, ROLE_MANAGEMENT)
    listing = create_listing_for(owner)

    response = client_for(owner).patch(
        f"/api/v1/listings/{listing.listing_id}/",
        {"description": "Updated draft", "features": ["updated"]},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["description"] == "Updated draft"
    assert response.data["features"] == ["updated"]

    Listing.objects.filter(pk=listing.pk).update(status=Listing.Status.ACTIVE)
    non_draft_response = client_for(owner).patch(
        f"/api/v1/listings/{listing.listing_id}/",
        {"description": "Denied"},
        format="json",
    )
    management_response = client_for(manager).patch(
        f"/api/v1/listings/{listing.listing_id}/",
        {"description": "Denied"},
        format="json",
    )
    Listing.objects.filter(pk=listing.pk).update(status=Listing.Status.DRAFT)
    UserRole.objects.filter(user=owner, role__code=ROLE_OWNER).update(is_active=False)
    revoked_response = client_for(owner).patch(
        f"/api/v1/listings/{listing.listing_id}/",
        {"description": "Denied"},
        format="json",
    )

    assert non_draft_response.status_code == 403
    assert management_response.status_code == 403
    assert revoked_response.status_code == 403


@pytest.mark.parametrize("status_value", [Listing.Status.ACTIVE, Listing.Status.WITHDRAWN, Listing.Status.SUSPENDED, Listing.Status.SOLD, Listing.Status.UNDER_OFFER])
def test_patch_rejects_direct_status_mutation(status_value):
    owner = create_user(f"listing-status-{status_value}@example.test")
    grant_role(owner, ROLE_OWNER)
    listing = create_listing_for(owner)

    response = client_for(owner).patch(
        f"/api/v1/listings/{listing.listing_id}/",
        {"status": status_value},
        format="json",
    )

    assert response.status_code == 400
    assert "status" in response.data


@pytest.mark.parametrize("field", ["property", "lister", "lister_kind", "currency", "listing_id"])
def test_patch_rejects_protected_fields(field):
    owner = create_user(f"listing-patch-protected-{field}@example.test")
    grant_role(owner, ROLE_OWNER)
    listing = create_listing_for(owner)

    response = client_for(owner).patch(
        f"/api/v1/listings/{listing.listing_id}/",
        {field: "hostile"},
        format="json",
    )

    assert response.status_code == 400
    assert field in response.data


def test_activate_endpoint_exists_but_fails_closed_and_unauthorized_is_denied():
    owner = create_user("listing-activate-owner@example.test")
    other = create_user("listing-activate-other@example.test")
    grant_role(owner, ROLE_OWNER)
    grant_role(other, ROLE_OWNER)
    listing = create_listing_for(owner)

    response = client_for(owner).post(f"/api/v1/listings/{listing.listing_id}/activate/", {}, format="json")
    other_response = client_for(other).post(f"/api/v1/listings/{listing.listing_id}/activate/", {}, format="json")

    listing.refresh_from_db()
    assert response.status_code == 400
    assert listing.status == Listing.Status.DRAFT
    assert other_response.status_code == 403


def test_withdraw_endpoint_uses_active_lister_lifecycle():
    owner = create_user("listing-withdraw-owner@example.test")
    other = create_user("listing-withdraw-other@example.test")
    grant_role(owner, ROLE_OWNER)
    grant_role(other, ROLE_OWNER)
    listing = create_listing_for(owner, status=Listing.Status.ACTIVE)

    other_response = client_for(other).post(f"/api/v1/listings/{listing.listing_id}/withdraw/", {}, format="json")
    response = client_for(owner).post(f"/api/v1/listings/{listing.listing_id}/withdraw/", {}, format="json")

    assert other_response.status_code == 403
    assert response.status_code == 200
    assert response.data["status"] == Listing.Status.WITHDRAWN


def test_management_suspend_endpoint_authorization_and_reason_validation():
    owner = create_user("listing-suspend-owner@example.test")
    manager = create_user("listing-suspend-manager@example.test")
    verifier = create_user("listing-suspend-verifier@example.test")
    grant_role(owner, ROLE_OWNER)
    grant_role(manager, ROLE_MANAGEMENT)
    grant_role(verifier, ROLE_VERIFIER)
    listing = create_listing_for(owner, status=Listing.Status.ACTIVE)

    owner_response = client_for(owner).post(f"/api/v1/management/listings/{listing.listing_id}/suspend/", {"reason": "Own"}, format="json")
    verifier_response = client_for(verifier).post(f"/api/v1/management/listings/{listing.listing_id}/suspend/", {"reason": "Review"}, format="json")
    blank_response = client_for(manager).post(f"/api/v1/management/listings/{listing.listing_id}/suspend/", {"reason": "   "}, format="json")
    response = client_for(manager).post(f"/api/v1/management/listings/{listing.listing_id}/suspend/", {"reason": "Policy"}, format="json")

    assert owner_response.status_code == 403
    assert verifier_response.status_code == 403
    assert blank_response.status_code == 400
    assert response.status_code == 200
    assert response.data["status"] == Listing.Status.SUSPENDED


def test_management_restore_endpoint_authorized_but_prerequisites_block_restoration():
    owner = create_user("listing-restore-owner@example.test")
    manager = create_user("listing-restore-manager@example.test")
    revoked_manager = create_user("listing-restore-revoked@example.test")
    grant_role(owner, ROLE_OWNER)
    grant_role(manager, ROLE_MANAGEMENT)
    grant_role(revoked_manager, ROLE_MANAGEMENT, is_active=False)
    listing = create_listing_for(owner, status=Listing.Status.SUSPENDED)

    revoked_response = client_for(revoked_manager).post(f"/api/v1/management/listings/{listing.listing_id}/restore/", {}, format="json")
    response = client_for(manager).post(f"/api/v1/management/listings/{listing.listing_id}/restore/", {}, format="json")

    listing.refresh_from_db()
    assert revoked_response.status_code == 403
    assert response.status_code == 400
    assert listing.status == Listing.Status.SUSPENDED


def test_role_revocation_api_matrix_for_owner_and_agent_listings():
    for role_code, lister_kind in [(ROLE_OWNER, Listing.ListerKind.OWNER), (ROLE_AGENT, Listing.ListerKind.AGENT)]:
        actor = create_user(f"listing-revoked-{role_code}@example.test")
        grant_role(actor, role_code)
        listing = create_listing_for(actor, lister_kind=lister_kind)
        UserRole.objects.filter(user=actor, role__code=role_code).update(is_active=False)

        assert client_for(actor).get("/api/v1/listings/").status_code == 200
        assert client_for(actor).get(f"/api/v1/listings/{listing.listing_id}/").status_code == 200
        assert client_for(actor).patch(f"/api/v1/listings/{listing.listing_id}/", {"description": "Denied"}, format="json").status_code == 403
        assert client_for(actor).post(f"/api/v1/listings/{listing.listing_id}/activate/", {}, format="json").status_code == 403
        Listing.objects.filter(pk=listing.pk).update(status=Listing.Status.ACTIVE)
        assert client_for(actor).post(f"/api/v1/listings/{listing.listing_id}/withdraw/", {}, format="json").status_code == 403


def test_privilege_escalation_attempts_fail_safely():
    owner = create_user("listing-escalation-owner@example.test")
    manager = create_user("listing-escalation-manager@example.test")
    grant_role(owner, ROLE_OWNER)
    grant_role(manager, ROLE_MANAGEMENT)
    owner.role = ROLE_MANAGEMENT
    owner.roles = [ROLE_MANAGEMENT]
    listing = create_listing_for(owner)
    other_property = create_property_record(created_by=manager)

    fake_claim_response = client_for(owner).post(
        f"/api/v1/management/listings/{listing.listing_id}/suspend/",
        {"reason": "I claim management"},
        format="json",
    )
    protected_lister_response = client_for(owner).post(
        "/api/v1/listings/",
        create_payload(create_property_record(created_by=owner), lister=str(manager.pk)),
        format="json",
    )
    unrelated_property_response = client_for(owner).post(
        "/api/v1/listings/",
        create_payload(other_property),
        format="json",
    )
    management_patch_response = client_for(manager).patch(
        f"/api/v1/listings/{listing.listing_id}/",
        {"description": "Management edit"},
        format="json",
    )

    assert fake_claim_response.status_code == 403
    assert protected_lister_response.status_code == 400
    assert unrelated_property_response.status_code == 403
    assert management_patch_response.status_code == 403


def test_unsupported_methods_and_deferred_lifecycle_routes_are_not_exposed():
    owner = create_user("listing-method-owner@example.test")
    grant_role(owner, ROLE_OWNER)
    listing = create_listing_for(owner)
    client = client_for(owner)

    assert client.put(f"/api/v1/listings/{listing.listing_id}/", {}, format="json").status_code == 405
    assert client.delete(f"/api/v1/listings/{listing.listing_id}/").status_code == 405
    assert client.post(f"/api/v1/listings/{listing.listing_id}/under-offer/", {}, format="json").status_code == 404
    assert client.post(f"/api/v1/listings/{listing.listing_id}/sold/", {}, format="json").status_code == 404
