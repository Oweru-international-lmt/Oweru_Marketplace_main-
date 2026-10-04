from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.gis.geos import Point
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIRequestFactory

from apps.listings import policies, services
from apps.listings.models import Listing
from apps.localities.models import District, Locality, Region, Ward
from apps.properties.models import PropertyRecord
from apps.roles.catalog import (
    CANONICAL_ROLE_CODES,
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
from apps.roles.permissions import (
    CanConfirmPayment,
    CanManageLead,
    CanManageVerification,
    CanViewSensitiveOwnerData,
    IsListingOwner,
)
from apps.roles.services import bootstrap_canonical_roles


pytestmark = pytest.mark.django_db


def create_user(email, *, is_active=True):
    return get_user_model().objects.create_user(
        email=email,
        phone=f"+2557{abs(hash(email)) % 100000000:08d}",
        full_name="Listing Auth User",
        password="StrongPass123!",
        is_active=is_active,
    )


def grant_role(user, role_code, *, is_active=True, role_active=True):
    bootstrap_canonical_roles()
    role = Role.objects.get(code=role_code)
    role.is_active = role_active
    role.save(update_fields=["is_active"])
    return UserRole.objects.create(user=user, role=role, is_active=is_active)


def request_for(user):
    request = APIRequestFactory().get("/internal/listings/")
    request.user = user
    return request


def create_hierarchy(prefix):
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


def create_property_record(*, created_by, prefix):
    region, district, ward, locality = create_hierarchy(prefix)
    return PropertyRecord.objects.create(
        property_id=f"OWR-{abs(hash(prefix)) % 10000000000000000:016d}",
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
    property_record = property_record or create_property_record(created_by=actor, prefix=f"AuthProp{actor.pk.hex[:8]}")
    selling_price = Decimal("120000000") if lister_kind == Listing.ListerKind.AGENT else Decimal("100000000")
    return Listing.objects.create(
        listing_id=f"LST-{abs(hash((actor.pk, status, lister_kind, property_record.pk))) % 10000000000000000:016d}",
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


def test_actor_validation_fails_closed_for_invalid_actors():
    lister = create_user("actor-validation-owner@example.test")
    deleted = create_user("actor-validation-deleted@example.test")
    grant_role(lister, ROLE_OWNER)
    listing = create_listing_for(lister)
    unsaved = get_user_model()(email="unsaved-auth@example.test")
    fake = type("FakeActor", (), {"is_authenticated": True, "pk": lister.pk, "is_active": True})()

    for actor in [None, AnonymousUser(), unsaved, fake]:
        assert policies.get_active_persisted_actor(actor) is None
        assert not policies.can_view_listing(actor, listing)
        assert not policies.can_update_listing(actor, listing)
        assert not policies.can_suspend_listing(actor, listing)

    deleted.delete()
    assert policies.get_active_persisted_actor(deleted) is None


@pytest.mark.parametrize(
    ("role_code", "owner_allowed", "agent_allowed"),
    [
        (ROLE_OWNER, True, False),
        (ROLE_AGENT, False, True),
        (ROLE_BUYER, False, False),
        (ROLE_MANAGEMENT, False, False),
        (ROLE_VERIFIER, False, False),
        (ROLE_MARKETER, False, False),
        (ROLE_PROFESSIONAL, False, False),
        (ROLE_LOCAL_OFFICIAL, False, False),
    ],
)
def test_create_policy_uses_selected_lister_kind_and_canonical_roles(role_code, owner_allowed, agent_allowed):
    actor = create_user(f"create-{role_code}@example.test")
    grant_role(actor, role_code)

    assert policies.can_create_listing(actor, lister_kind=Listing.ListerKind.OWNER) is owner_allowed
    assert policies.can_create_listing(actor, lister_kind=Listing.ListerKind.AGENT) is agent_allowed


def test_dual_role_user_can_choose_owner_or_agent_create_policy():
    actor = create_user("dual-create-policy@example.test")
    grant_role(actor, ROLE_OWNER)
    grant_role(actor, ROLE_AGENT)

    assert policies.can_create_listing(actor, lister_kind=Listing.ListerKind.OWNER)
    assert policies.can_create_listing(actor, lister_kind=Listing.ListerKind.AGENT)


def test_private_view_policy_allows_historical_lister_and_management_only():
    lister = create_user("view-lister@example.test")
    other = create_user("view-other@example.test")
    manager = create_user("view-manager@example.test")
    revoked_manager = create_user("view-revoked-manager@example.test")
    inactive_lister = create_user("view-inactive-lister@example.test", is_active=False)
    grant_role(lister, ROLE_OWNER)
    grant_role(other, ROLE_OWNER)
    grant_role(manager, ROLE_MANAGEMENT)
    grant_role(revoked_manager, ROLE_MANAGEMENT, is_active=False)
    grant_role(inactive_lister, ROLE_OWNER)
    listing = create_listing_for(lister)
    inactive_listing = create_listing_for(inactive_lister)
    UserRole.objects.filter(user=lister, role__code=ROLE_OWNER).update(is_active=False)

    assert policies.can_view_listing(lister, listing)
    assert policies.can_view_listing(manager, listing)
    assert not policies.can_view_listing(other, listing)
    assert not policies.can_view_listing(revoked_manager, listing)
    assert not policies.can_view_listing(inactive_lister, inactive_listing)


@pytest.mark.parametrize(("role_code", "lister_kind"), [(ROLE_OWNER, Listing.ListerKind.OWNER), (ROLE_AGENT, Listing.ListerKind.AGENT)])
def test_role_revocation_preserves_view_but_blocks_update_activation_and_withdraw(role_code, lister_kind):
    actor = create_user(f"revocation-{role_code}@example.test")
    grant_role(actor, role_code)
    listing = create_listing_for(actor, lister_kind=lister_kind, status=Listing.Status.DRAFT)

    assert policies.can_view_listing(actor, listing)
    assert policies.can_update_listing(actor, listing)
    assert policies.can_activate_listing(actor, listing)
    Listing.objects.filter(pk=listing.pk).update(status=Listing.Status.ACTIVE)
    listing.refresh_from_db()
    assert policies.can_withdraw_listing(actor, listing)

    UserRole.objects.filter(user=actor, role__code=role_code).update(is_active=False)

    assert policies.can_view_listing(actor, listing)
    assert not policies.can_update_listing(actor, listing)
    assert not policies.can_activate_listing(actor, listing)
    assert not policies.can_withdraw_listing(actor, listing)
    with pytest.raises(PermissionDenied):
        services.update_listing(actor=actor, listing=listing, description="Denied")
    with pytest.raises(PermissionDenied):
        services.withdraw_listing(actor=actor, listing=listing)


def test_management_matrix_distinguishes_inspection_from_ownership_and_content_editing():
    lister = create_user("management-listing-lister@example.test")
    manager = create_user("management-listing-manager@example.test")
    revoked_manager = create_user("management-listing-revoked@example.test")
    inactive_manager = create_user("management-listing-inactive@example.test", is_active=False)
    grant_role(lister, ROLE_OWNER)
    grant_role(manager, ROLE_MANAGEMENT)
    grant_role(revoked_manager, ROLE_MANAGEMENT, is_active=False)
    grant_role(inactive_manager, ROLE_MANAGEMENT)
    listing = create_listing_for(lister, status=Listing.Status.ACTIVE)

    assert policies.can_view_listing(manager, listing)
    assert not policies.can_update_listing(manager, listing)
    assert policies.can_suspend_listing(manager, listing)
    assert policies.can_restore_listing(manager, listing)
    assert not IsListingOwner().has_object_permission(request_for(manager), view=None, obj=listing)

    for denied in [revoked_manager, inactive_manager]:
        assert list(policies.get_accessible_listings(denied)) == []
        assert not policies.can_view_listing(denied, listing)
        assert not policies.can_suspend_listing(denied, listing)
        assert not policies.can_restore_listing(denied, listing)


def test_listing_ownership_is_listing_lister_not_property_creator():
    property_creator = create_user("property-creator-auth@example.test")
    listing_lister = create_user("actual-listing-lister@example.test")
    grant_role(property_creator, ROLE_OWNER)
    grant_role(listing_lister, ROLE_OWNER)
    property_record = create_property_record(created_by=property_creator, prefix="OwnershipBoundary")
    listing = create_listing_for(listing_lister, property_record=property_record)

    assert listing.property.created_by == property_creator
    assert policies.is_listing_lister(listing_lister, listing)
    assert not policies.is_listing_lister(property_creator, listing)
    assert not IsListingOwner().has_object_permission(request_for(property_creator), view=None, obj=listing)


def test_queryset_visibility_does_not_leak_unrelated_listings():
    first = create_user("visibility-first@example.test")
    second = create_user("visibility-second@example.test")
    buyer = create_user("visibility-buyer@example.test")
    manager = create_user("visibility-manager@example.test")
    inactive = create_user("visibility-inactive@example.test", is_active=False)
    grant_role(first, ROLE_OWNER)
    grant_role(second, ROLE_OWNER)
    grant_role(buyer, ROLE_BUYER)
    grant_role(manager, ROLE_MANAGEMENT)
    grant_role(inactive, ROLE_OWNER)
    first_listing = create_listing_for(first)
    second_listing = create_listing_for(second)
    inactive_listing = create_listing_for(inactive)
    UserRole.objects.filter(user=first, role__code=ROLE_OWNER).update(is_active=False)

    assert list(policies.get_accessible_listings(first)) == [first_listing]
    assert list(policies.get_accessible_listings(second)) == [second_listing]
    assert list(policies.get_accessible_listings(buyer)) == []
    assert set(policies.get_accessible_listings(manager)) == {first_listing, second_listing, inactive_listing}
    assert list(policies.get_accessible_listings(inactive)) == []
    assert list(policies.get_accessible_listings(AnonymousUser())) == []


def test_fake_claims_and_duck_typed_objects_do_not_authorize():
    actor = create_user("fake-claims-listing@example.test")
    grant_role(actor, ROLE_BUYER)
    actor.role = ROLE_MANAGEMENT
    actor.roles = [ROLE_OWNER, ROLE_MANAGEMENT]
    actor.jwt = {"roles": [ROLE_MANAGEMENT]}
    fake_listing = type("FakeListing", (), {"lister": actor, "lister_id": actor.pk})()

    assert not policies.can_create_listing(actor, lister_kind=Listing.ListerKind.OWNER)
    assert not policies.can_suspend_listing(actor, fake_listing)
    assert not IsListingOwner().has_object_permission(request_for(actor), view=None, obj=fake_listing)


def test_is_listing_owner_permission_view_and_object_behavior():
    lister = create_user("permission-lister@example.test")
    other = create_user("permission-other@example.test")
    manager = create_user("permission-manager@example.test")
    inactive = create_user("permission-inactive@example.test", is_active=False)
    grant_role(lister, ROLE_OWNER)
    grant_role(other, ROLE_OWNER)
    grant_role(manager, ROLE_MANAGEMENT)
    grant_role(inactive, ROLE_OWNER)
    listing = create_listing_for(lister)
    permission = IsListingOwner()

    assert permission.has_permission(request_for(lister), view=None)
    assert not permission.has_permission(request_for(inactive), view=None)
    assert not permission.has_permission(request_for(AnonymousUser()), view=None)
    assert permission.has_object_permission(request_for(lister), view=None, obj=listing)
    assert not permission.has_object_permission(request_for(other), view=None, obj=listing)
    assert not permission.has_object_permission(request_for(manager), view=None, obj=listing)
    assert not permission.has_object_permission(request_for(lister), view=None, obj=object())


@pytest.mark.parametrize("permission", [CanViewSensitiveOwnerData(), CanManageLead(), CanConfirmPayment(), CanManageVerification()])
def test_other_deferred_permissions_remain_fail_closed(permission):
    user = create_user("still-deferred@example.test")
    for role_code in CANONICAL_ROLE_CODES:
        UserRole.objects.create(user=user, role=Role.objects.get(code=role_code))

    assert not permission.has_permission(request_for(user), view=None)
    assert not permission.has_object_permission(request_for(user), view=None, obj=object())


def test_service_regressions_use_policy_without_enabling_activation():
    actor = create_user("service-policy-regression@example.test")
    manager = create_user("service-policy-manager@example.test")
    grant_role(actor, ROLE_OWNER)
    grant_role(manager, ROLE_MANAGEMENT)
    listing = services.create_listing(
        actor=actor,
        property_record=create_property_record(created_by=actor, prefix="ServicePolicy"),
        lister_kind=Listing.ListerKind.OWNER,
        selling_price=Decimal("100000000"),
        owner_price=Decimal("100000000"),
    )

    assert services.get_listing(actor=actor, listing_id=listing.listing_id) == listing
    services.update_listing(actor=actor, listing=listing, description="Still draft")
    with pytest.raises(ValidationError):
        services.activate_listing(actor=actor, listing=listing)

    Listing.objects.filter(pk=listing.pk).update(status=Listing.Status.ACTIVE)
    listing.refresh_from_db()
    assert services.withdraw_listing(actor=actor, listing=listing).status == Listing.Status.WITHDRAWN
    Listing.objects.filter(pk=listing.pk).update(status=Listing.Status.ACTIVE)
    listing.refresh_from_db()
    assert services.suspend_listing(actor=manager, listing=listing, reason="Policy").status == Listing.Status.SUSPENDED
    with pytest.raises(ValidationError):
        services.restore_listing(actor=manager, listing=listing)
