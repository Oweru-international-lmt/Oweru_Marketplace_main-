from decimal import Decimal
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.gis.geos import Point
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.lister_identity.models import ListerIdentity
from apps.listings import services
from apps.listings.lifecycle import (
    LISTING_LIFECYCLE_TRANSITIONS,
    is_terminal_status,
    is_transition_documented,
)
from apps.listings.models import Listing
from apps.localities.models import District, Locality, Region, Ward
from apps.properties.models import PropertyRecord
from apps.roles.catalog import ROLE_AGENT, ROLE_BUYER, ROLE_MANAGEMENT, ROLE_OWNER
from apps.roles.models import Role, UserRole
from apps.roles.services import bootstrap_canonical_roles, user_has_role


pytestmark = pytest.mark.django_db


def create_user(email=None, *, is_active=True):
    email = email or f"listing-service-{uuid.uuid4().hex[:10]}@example.test"
    return get_user_model().objects.create_user(
        email=email,
        phone=f"+2557{abs(hash(email)) % 100000000:08d}",
        full_name="Listing Service User",
        password="StrongPass123!",
        is_active=is_active,
    )


def grant_role(user, role_code, *, is_active=True, role_active=True):
    bootstrap_canonical_roles()
    role = Role.objects.get(code=role_code)
    role.is_active = role_active
    role.save(update_fields=["is_active"])
    return UserRole.objects.create(user=user, role=role, is_active=is_active)


def create_hierarchy(prefix=None):
    prefix = prefix or f"ListingService{uuid.uuid4().hex[:8]}"
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


def create_property_record(*, created_by=None, prefix=None):
    prefix = prefix or f"ListingProp{uuid.uuid4().hex[:8]}"
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
        created_by=created_by or create_user(),
    )


def create_listing_for(actor, *, lister_kind=Listing.ListerKind.OWNER, status=Listing.Status.DRAFT, **overrides):
    property_record = overrides.pop("property", None) or create_property_record(created_by=actor)
    attrs = {
        "listing_id": f"LST-{uuid.uuid4().hex[:16].upper()}",
        "property": property_record,
        "lister": actor,
        "lister_kind": lister_kind,
        "selling_price": Decimal("100000000"),
        "owner_price": Decimal("100000000"),
        "currency": Listing.Currency.TZS,
        "status": status,
        "description": "Existing draft listing.",
        "features": ["road access"],
    }
    if lister_kind == Listing.ListerKind.AGENT:
        attrs["selling_price"] = Decimal("120000000")
        attrs["owner_price"] = Decimal("100000000")
    attrs.update(overrides)
    return Listing.objects.create(**attrs)


def create_verified_lister_identity(user):
    return ListerIdentity.objects.create(
        user=user,
        national_id_number=f"NIDA-{uuid.uuid4().hex[:12]}",
        national_id_photo_ref="identity/photo.jpg",
        live_selfie_ref="identity/selfie.jpg",
        status=ListerIdentity.Status.APPROVED,
        reviewed_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(days=30),
    )


def create_service_listing(actor, *, lister_kind=Listing.ListerKind.OWNER, property_record=None, **overrides):
    attrs = {
        "actor": actor,
        "property_record": property_record or create_property_record(created_by=actor),
        "lister_kind": lister_kind,
        "selling_price": Decimal("100000000"),
        "owner_price": Decimal("100000000"),
        "description": "Near main road.",
        "features": ["road access", {"note": "json compatible"}],
    }
    if lister_kind == Listing.ListerKind.AGENT:
        attrs["selling_price"] = Decimal("120000000")
        attrs["owner_price"] = Decimal("100000000")
    attrs.update(overrides)
    return services.create_listing(**attrs)


def test_owner_creates_owner_draft_listing():
    actor = create_user("owner-listing@example.test")
    grant_role(actor, ROLE_OWNER)

    listing = create_service_listing(actor, lister_kind=Listing.ListerKind.OWNER)

    assert listing.lister == actor
    assert listing.lister_kind == Listing.ListerKind.OWNER
    assert listing.status == Listing.Status.DRAFT
    assert listing.currency == Listing.Currency.TZS
    assert listing.listing_id.startswith("LST-")
    assert not listing.listing_id.startswith("OWR-")


def test_agent_creates_agent_draft_listing():
    actor = create_user("agent-listing@example.test")
    grant_role(actor, ROLE_AGENT)

    listing = create_service_listing(actor, lister_kind=Listing.ListerKind.AGENT)

    assert listing.lister == actor
    assert listing.lister_kind == Listing.ListerKind.AGENT
    assert listing.status == Listing.Status.DRAFT


def test_lister_kind_requires_matching_canonical_role():
    owner = create_user("owner-only@example.test")
    grant_role(owner, ROLE_OWNER)
    agent = create_user("agent-only@example.test")
    grant_role(agent, ROLE_AGENT)

    with pytest.raises(PermissionDenied):
        create_service_listing(owner, lister_kind=Listing.ListerKind.AGENT)
    with pytest.raises(PermissionDenied):
        create_service_listing(agent, lister_kind=Listing.ListerKind.OWNER)


def test_dual_role_user_can_create_either_lister_kind():
    actor = create_user("dual-role@example.test")
    grant_role(actor, ROLE_OWNER)
    grant_role(actor, ROLE_AGENT)

    owner_listing = create_service_listing(actor, lister_kind=Listing.ListerKind.OWNER)
    agent_listing = create_service_listing(actor, lister_kind=Listing.ListerKind.AGENT)

    assert owner_listing.lister_kind == Listing.ListerKind.OWNER
    assert agent_listing.lister_kind == Listing.ListerKind.AGENT


@pytest.mark.parametrize("role_code", [ROLE_BUYER, ROLE_MANAGEMENT])
def test_buyer_or_management_only_cannot_create(role_code):
    actor = create_user(f"{role_code}-listing@example.test")
    grant_role(actor, role_code)

    with pytest.raises(PermissionDenied):
        create_service_listing(actor)


def test_inactive_user_revoked_role_inactive_role_and_inactive_assignment_are_denied():
    inactive = create_user("inactive-listing@example.test", is_active=False)
    grant_role(inactive, ROLE_OWNER)
    with pytest.raises(PermissionDenied):
        create_service_listing(inactive)

    revoked = create_user("revoked-listing@example.test")
    grant_role(revoked, ROLE_OWNER, is_active=False)
    with pytest.raises(PermissionDenied):
        create_service_listing(revoked)

    inactive_role = create_user("inactive-role-listing@example.test")
    grant_role(inactive_role, ROLE_OWNER, role_active=False)
    with pytest.raises(PermissionDenied):
        create_service_listing(inactive_role)

    inactive_assignment = create_user("inactive-assignment-listing@example.test")
    grant_role(inactive_assignment, ROLE_OWNER, is_active=False)
    with pytest.raises(PermissionDenied):
        create_service_listing(inactive_assignment)


def test_fake_client_role_claims_and_unpersisted_actors_are_denied():
    valid_owner = create_user("valid-property-owner@example.test")
    grant_role(valid_owner, ROLE_OWNER)
    property_record = create_property_record(created_by=valid_owner)
    actor = create_user("fake-claim@example.test")
    actor.role = ROLE_OWNER
    actor.roles = [ROLE_OWNER]
    with pytest.raises(PermissionDenied):
        create_service_listing(actor, property_record=property_record)

    unsaved = get_user_model()(email="unsaved-listing@example.test")
    with pytest.raises(PermissionDenied):
        create_service_listing(unsaved, property_record=property_record)

    with pytest.raises(PermissionDenied):
        create_service_listing(AnonymousUser(), property_record=property_record)


@pytest.mark.parametrize("field", ["lister", "status", "listing_id"])
def test_create_rejects_client_controlled_fields(field):
    actor = create_user(f"{field}-control@example.test")
    other = create_user(f"{field}-other@example.test")
    grant_role(actor, ROLE_OWNER)
    value = {"lister": other, "status": Listing.Status.ACTIVE, "listing_id": "CLIENT-CHOSEN"}[field]

    with pytest.raises(ValidationError):
        create_service_listing(actor, **{field: value})

    assert not Listing.objects.filter(listing_id="CLIENT-CHOSEN").exists()


def test_listing_id_is_unique_and_collision_retry_works(monkeypatch):
    actor = create_user("collision-listing@example.test")
    grant_role(actor, ROLE_OWNER)
    existing = create_listing_for(actor, listing_id="LST-COLLISION000001")
    tokens = iter([existing.listing_id.removeprefix("LST-"), "UNIQUE0000000001"])
    monkeypatch.setattr(services, "_listing_id_token", lambda: next(tokens))

    listing = create_service_listing(actor)

    assert listing.listing_id == "LST-UNIQUE0000000001"
    assert Listing.objects.filter(listing_id=listing.listing_id).count() == 1


def test_bounded_listing_id_collision_failure(monkeypatch):
    actor = create_user("collision-failure@example.test")
    grant_role(actor, ROLE_OWNER)
    create_listing_for(actor, listing_id="LST-COLLISION000002")
    monkeypatch.setattr(services, "_listing_id_token", lambda: "COLLISION000002")

    with pytest.raises(ValidationError):
        create_service_listing(actor)


def test_lister_can_create_against_own_property_only_and_management_has_no_override():
    actor = create_user("own-property-listing@example.test")
    other = create_user("other-property-listing@example.test")
    manager = create_user("manager-property-listing@example.test")
    grant_role(actor, ROLE_OWNER)
    grant_role(other, ROLE_OWNER)
    grant_role(manager, ROLE_MANAGEMENT)
    grant_role(manager, ROLE_OWNER)
    own_property = create_property_record(created_by=actor)
    other_property = create_property_record(created_by=other)

    assert create_service_listing(actor, property_record=own_property).property == own_property
    with pytest.raises(PermissionDenied):
        create_service_listing(actor, property_record=other_property)
    with pytest.raises(PermissionDenied):
        create_service_listing(manager, property_record=other_property)


@pytest.mark.parametrize(
    "overrides",
    [
        {"selling_price": Decimal("0")},
        {"owner_price": Decimal("-1")},
        {"lister_kind": Listing.ListerKind.OWNER, "selling_price": Decimal("100"), "owner_price": Decimal("99")},
        {"lister_kind": Listing.ListerKind.AGENT, "selling_price": Decimal("99"), "owner_price": Decimal("100")},
        {"lister_kind": "MANAGEMENT"},
    ],
)
def test_create_enforces_model_price_and_lister_kind_invariants(overrides):
    actor = create_user(f"price-{uuid.uuid4().hex[:8]}@example.test")
    grant_role(actor, ROLE_OWNER)
    grant_role(actor, ROLE_AGENT)

    with pytest.raises(ValidationError):
        create_service_listing(actor, **overrides)


def test_description_features_persist_and_unsupported_future_fields_are_rejected():
    actor = create_user("features-listing@example.test")
    grant_role(actor, ROLE_OWNER)

    listing = create_service_listing(
        actor,
        description="Quiet plot near school.",
        features=["corner", {"access": "road"}],
    )

    assert listing.description == "Quiet plot near school."
    assert listing.features == ["corner", {"access": "road"}]
    with pytest.raises(ValidationError):
        create_service_listing(actor, photos=["image.jpg"])
    with pytest.raises(ValidationError):
        create_service_listing(actor, currency="USD")


def test_update_allows_lister_to_modify_mutable_fields_only_for_draft():
    actor = create_user("update-listing@example.test")
    grant_role(actor, ROLE_AGENT)
    listing = create_service_listing(actor, lister_kind=Listing.ListerKind.AGENT)

    updated = services.update_listing(
        actor=actor,
        listing=listing,
        selling_price=Decimal("130000000"),
        description="Updated draft.",
        features=["updated", {"near": "school"}],
    )

    assert updated.selling_price == Decimal("130000000")
    assert updated.description == "Updated draft."
    assert updated.features == ["updated", {"near": "school"}]


def test_update_enforces_price_invariants_and_failed_update_leaves_listing_unchanged():
    actor = create_user("failed-update-listing@example.test")
    grant_role(actor, ROLE_OWNER)
    listing = create_service_listing(actor)

    with pytest.raises(ValidationError):
        services.update_listing(actor=actor, listing=listing, selling_price=Decimal("120000000"))

    listing.refresh_from_db()
    assert listing.selling_price == Decimal("100000000")
    assert listing.owner_price == Decimal("100000000")


@pytest.mark.parametrize("field", ["listing_id", "lister", "property", "lister_kind", "status", "currency", "created_at", "updated_at"])
def test_update_rejects_immutable_fields(field):
    actor = create_user(f"immutable-{field}@example.test")
    grant_role(actor, ROLE_OWNER)
    listing = create_service_listing(actor)
    value = {
        "listing_id": "CLIENT-UPDATE",
        "lister": create_user(f"new-lister-{field}@example.test"),
        "property": create_property_record(created_by=actor),
        "lister_kind": Listing.ListerKind.AGENT,
        "status": Listing.Status.ACTIVE,
        "currency": "USD",
        "created_at": listing.created_at,
        "updated_at": listing.updated_at,
    }[field]

    with pytest.raises(ValidationError):
        services.update_listing(actor=actor, listing=listing, **{field: value})


def test_update_denies_unrelated_management_revoked_and_inactive_actors():
    actor = create_user("draft-owner@example.test")
    other = create_user("draft-other@example.test")
    manager = create_user("draft-manager@example.test")
    revoked = create_user("draft-revoked@example.test")
    inactive = create_user("draft-inactive@example.test", is_active=False)
    grant_role(actor, ROLE_OWNER)
    grant_role(other, ROLE_OWNER)
    grant_role(manager, ROLE_MANAGEMENT)
    grant_role(revoked, ROLE_OWNER, is_active=False)
    grant_role(inactive, ROLE_OWNER)
    listing = create_service_listing(actor)

    for denied in [other, manager, revoked, inactive]:
        with pytest.raises(PermissionDenied):
            services.update_listing(actor=denied, listing=listing, description="Denied")


def test_update_denies_non_draft_listing_and_removed_role_no_longer_authorizes():
    actor = create_user("non-draft-update@example.test")
    grant_role(actor, ROLE_OWNER)
    listing = create_service_listing(actor)
    Listing.objects.filter(pk=listing.pk).update(status=Listing.Status.ACTIVE)

    with pytest.raises(PermissionDenied):
        services.update_listing(actor=actor, listing=listing, description="Denied")

    draft = create_service_listing(actor)
    UserRole.objects.filter(user=actor, role__code=ROLE_OWNER).update(is_active=False)
    assert not user_has_role(actor, ROLE_OWNER)
    with pytest.raises(PermissionDenied):
        services.update_listing(actor=actor, listing=draft, description="Denied")


def test_get_listing_allows_lister_and_active_management_only():
    actor = create_user("get-lister@example.test")
    other = create_user("get-other@example.test")
    manager = create_user("get-manager@example.test")
    inactive_manager = create_user("get-inactive-manager@example.test")
    grant_role(actor, ROLE_OWNER)
    grant_role(other, ROLE_OWNER)
    grant_role(manager, ROLE_MANAGEMENT)
    grant_role(inactive_manager, ROLE_MANAGEMENT, is_active=False)
    listing = create_service_listing(actor)

    assert services.get_listing(actor=actor, listing_id=listing.listing_id) == listing
    assert services.get_listing(actor=manager, listing_id=listing.listing_id) == listing
    with pytest.raises(PermissionDenied):
        services.get_listing(actor=other, listing_id=listing.listing_id)
    with pytest.raises(PermissionDenied):
        services.get_listing(actor=inactive_manager, listing_id=listing.listing_id)
    with pytest.raises(PermissionDenied):
        services.get_listing(actor=AnonymousUser(), listing_id=listing.listing_id)
    with pytest.raises(NotFound):
        services.get_listing(actor=actor, listing_id="LST-DOESNOTEXIST")


def test_get_accessible_listings_scopes_to_actor_or_management():
    first = create_user("visible-first@example.test")
    second = create_user("visible-second@example.test")
    manager = create_user("visible-manager@example.test")
    inactive = create_user("visible-inactive@example.test", is_active=False)
    grant_role(first, ROLE_OWNER)
    grant_role(second, ROLE_OWNER)
    grant_role(manager, ROLE_MANAGEMENT)
    first_listing = create_service_listing(first)
    second_listing = create_service_listing(second)

    assert list(services.get_accessible_listings(first)) == [first_listing]
    assert set(services.get_accessible_listings(manager)) == {first_listing, second_listing}
    assert list(services.get_accessible_listings(inactive)) == []
    assert list(services.get_accessible_listings(AnonymousUser())) == []


def test_property_record_boundary_is_not_mutated_by_listing_creation():
    actor = create_user("property-boundary-listing@example.test")
    grant_role(actor, ROLE_OWNER)
    property_record = create_property_record(created_by=actor)
    before = {
        "property_id": property_record.property_id,
        "locality_id": property_record.locality_id,
        "pin": property_record.pin.clone(),
        "created_by_id": property_record.created_by_id,
    }

    listing = create_service_listing(actor, property_record=property_record)
    property_record.refresh_from_db()

    assert listing.property == property_record
    assert property_record.property_id == before["property_id"]
    assert property_record.locality_id == before["locality_id"]
    assert property_record.pin.equals_exact(before["pin"], tolerance=0)
    assert property_record.created_by_id == before["created_by_id"]


def test_no_status_transition_lister_identity_phone_media_or_audit_boundaries():
    forbidden_service_names = {
        "mark_under_offer",
        "mark_sold",
    }
    forbidden_import_markers = {"ListerIdentity", "create_audit_log", "legacy_event_stream", "legacy_authorization"}
    service_source = services.__dict__

    assert forbidden_service_names.isdisjoint(service_source)
    assert forbidden_import_markers.isdisjoint(set(str(value) for value in service_source.values()))


def test_lifecycle_policy_documents_state_machine_and_sold_is_terminal():
    assert is_transition_documented(Listing.Status.DRAFT, Listing.Status.ACTIVE)
    assert is_transition_documented(Listing.Status.ACTIVE, Listing.Status.UNDER_OFFER)
    assert is_transition_documented(Listing.Status.ACTIVE, Listing.Status.WITHDRAWN)
    assert is_transition_documented(Listing.Status.ACTIVE, Listing.Status.SUSPENDED)
    assert is_transition_documented(Listing.Status.UNDER_OFFER, Listing.Status.SOLD)
    assert is_transition_documented(Listing.Status.UNDER_OFFER, Listing.Status.ACTIVE)
    assert is_transition_documented(Listing.Status.WITHDRAWN, Listing.Status.ACTIVE)
    assert is_transition_documented(Listing.Status.SUSPENDED, Listing.Status.ACTIVE)
    assert is_terminal_status(Listing.Status.SOLD)
    assert LISTING_LIFECYCLE_TRANSITIONS[Listing.Status.SOLD] == frozenset()
    assert not is_transition_documented(Listing.Status.DRAFT, Listing.Status.WITHDRAWN)
    assert not is_transition_documented(Listing.Status.SOLD, Listing.Status.ACTIVE)


def test_activation_eligibility_fails_closed_without_media_and_phone_proof():
    actor = create_user("activation-closed@example.test")
    grant_role(actor, ROLE_OWNER)
    listing = create_service_listing(actor)

    eligibility = services.check_listing_activation_eligibility(listing=listing)

    assert not eligibility.is_eligible
    assert "lister_identity_verified" in eligibility.blocked_codes
    assert "lister_phone_confirmed" in eligibility.blocked_codes
    assert "listing_required_media" in eligibility.blocked_codes
    assert not hasattr(listing, "phone_confirmed")
    assert not hasattr(listing, "media_count")


def test_verified_identity_alone_does_not_activate_draft_listing():
    actor = create_user("verified-alone@example.test")
    grant_role(actor, ROLE_OWNER)
    create_verified_lister_identity(actor)
    listing = create_service_listing(actor)

    with pytest.raises(ValidationError) as exc:
        services.activate_listing(actor=actor, listing=listing)

    listing.refresh_from_db()
    assert listing.status == Listing.Status.DRAFT
    assert "lister_phone_confirmed" in exc.value.detail["activation"]
    assert "listing_required_media" in exc.value.detail["activation"]
    assert "lister_identity_verified" not in exc.value.detail["activation"]


def test_valid_role_alone_does_not_activate_and_status_is_unchanged():
    actor = create_user("role-alone@example.test")
    grant_role(actor, ROLE_OWNER)
    listing = create_service_listing(actor)

    with pytest.raises(ValidationError):
        services.activate_listing(actor=actor, listing=listing)

    listing.refresh_from_db()
    assert listing.status == Listing.Status.DRAFT


def test_withdraw_listing_active_lister_only_and_changes_status_only():
    actor = create_user("withdraw-lister@example.test")
    grant_role(actor, ROLE_OWNER)
    listing = create_listing_for(actor, status=Listing.Status.ACTIVE)
    before = {
        "selling_price": listing.selling_price,
        "owner_price": listing.owner_price,
        "description": listing.description,
        "features": listing.features,
        "property_id": listing.property_id,
        "lister_id": listing.lister_id,
        "lister_kind": listing.lister_kind,
        "currency": listing.currency,
    }

    withdrawn = services.withdraw_listing(actor=actor, listing=listing)

    assert withdrawn.status == Listing.Status.WITHDRAWN
    withdrawn.refresh_from_db()
    for field, value in before.items():
        assert getattr(withdrawn, field) == value


def test_withdraw_listing_denies_unrelated_revoked_inactive_wrong_state_and_sold():
    actor = create_user("withdraw-owner@example.test")
    other = create_user("withdraw-other@example.test")
    revoked = create_user("withdraw-revoked@example.test")
    inactive = create_user("withdraw-inactive@example.test", is_active=False)
    grant_role(actor, ROLE_OWNER)
    grant_role(other, ROLE_OWNER)
    grant_role(revoked, ROLE_OWNER, is_active=False)
    grant_role(inactive, ROLE_OWNER)
    active = create_listing_for(actor, status=Listing.Status.ACTIVE)

    for denied in [other, revoked, inactive]:
        with pytest.raises(PermissionDenied):
            services.withdraw_listing(actor=denied, listing=active)

    for status in [Listing.Status.DRAFT, Listing.Status.UNDER_OFFER, Listing.Status.SUSPENDED, Listing.Status.SOLD]:
        listing = create_listing_for(actor, status=status)
        with pytest.raises(ValidationError):
            services.withdraw_listing(actor=actor, listing=listing)
        listing.refresh_from_db()
        assert listing.status == status


def test_suspend_listing_requires_active_management_reason_and_active_source():
    lister = create_user("suspend-lister@example.test")
    manager = create_user("suspend-manager@example.test")
    grant_role(lister, ROLE_OWNER)
    grant_role(manager, ROLE_MANAGEMENT)
    listing = create_listing_for(lister, status=Listing.Status.ACTIVE)
    before_price = listing.selling_price

    suspended = services.suspend_listing(actor=manager, listing=listing, reason="Policy violation")

    assert suspended.status == Listing.Status.SUSPENDED
    suspended.refresh_from_db()
    assert suspended.selling_price == before_price


def test_suspend_listing_denies_non_management_revoked_inactive_empty_reason_and_wrong_state():
    lister = create_user("suspend-denied-lister@example.test")
    other = create_user("suspend-denied-other@example.test")
    revoked_manager = create_user("suspend-revoked-manager@example.test")
    inactive_manager = create_user("suspend-inactive-manager@example.test", is_active=False)
    manager = create_user("suspend-state-manager@example.test")
    grant_role(lister, ROLE_OWNER)
    grant_role(other, ROLE_OWNER)
    grant_role(revoked_manager, ROLE_MANAGEMENT, is_active=False)
    grant_role(inactive_manager, ROLE_MANAGEMENT)
    grant_role(manager, ROLE_MANAGEMENT)
    active = create_listing_for(lister, status=Listing.Status.ACTIVE)

    for denied in [lister, other, revoked_manager, inactive_manager]:
        with pytest.raises(PermissionDenied):
            services.suspend_listing(actor=denied, listing=active, reason="Reason")

    for reason in ["", "   ", None]:
        with pytest.raises(ValidationError):
            services.suspend_listing(actor=manager, listing=active, reason=reason)

    for status in [Listing.Status.DRAFT, Listing.Status.UNDER_OFFER, Listing.Status.WITHDRAWN, Listing.Status.SUSPENDED, Listing.Status.SOLD]:
        listing = create_listing_for(lister, status=status)
        with pytest.raises(ValidationError):
            services.suspend_listing(actor=manager, listing=listing, reason="Reason")
        listing.refresh_from_db()
        assert listing.status == status


def test_restore_listing_requires_management_and_activation_eligibility_without_bypass():
    lister = create_user("restore-lister@example.test")
    manager = create_user("restore-manager@example.test")
    other = create_user("restore-other@example.test")
    revoked_manager = create_user("restore-revoked-manager@example.test")
    inactive_manager = create_user("restore-inactive-manager@example.test", is_active=False)
    grant_role(lister, ROLE_OWNER)
    grant_role(manager, ROLE_MANAGEMENT)
    grant_role(other, ROLE_OWNER)
    grant_role(revoked_manager, ROLE_MANAGEMENT, is_active=False)
    grant_role(inactive_manager, ROLE_MANAGEMENT)
    listing = create_listing_for(lister, status=Listing.Status.SUSPENDED)

    for denied in [lister, other, revoked_manager, inactive_manager]:
        with pytest.raises(PermissionDenied):
            services.restore_listing(actor=denied, listing=listing)

    with pytest.raises(ValidationError) as exc:
        services.restore_listing(actor=manager, listing=listing)
    listing.refresh_from_db()
    assert listing.status == Listing.Status.SUSPENDED
    assert "lister_phone_confirmed" in exc.value.detail["activation"]
    assert "listing_required_media" in exc.value.detail["activation"]


def test_restore_listing_only_accepts_suspended_source():
    lister = create_user("restore-source-lister@example.test")
    manager = create_user("restore-source-manager@example.test")
    grant_role(lister, ROLE_OWNER)
    grant_role(manager, ROLE_MANAGEMENT)

    for status in [Listing.Status.DRAFT, Listing.Status.ACTIVE, Listing.Status.UNDER_OFFER, Listing.Status.WITHDRAWN, Listing.Status.SOLD]:
        listing = create_listing_for(lister, status=status)
        with pytest.raises(ValidationError):
            services.restore_listing(actor=manager, listing=listing)
        listing.refresh_from_db()
        assert listing.status == status


def test_under_offer_and_sold_operational_services_are_deferred_and_update_cannot_set_status():
    actor = create_user("deferred-status@example.test")
    grant_role(actor, ROLE_OWNER)
    listing = create_service_listing(actor)

    assert not hasattr(services, "mark_under_offer")
    assert not hasattr(services, "mark_sold")
    with pytest.raises(ValidationError):
        services.update_listing(actor=actor, listing=listing, status=Listing.Status.UNDER_OFFER)
    with pytest.raises(ValidationError):
        services.update_listing(actor=actor, listing=listing, status=Listing.Status.SOLD)
    assert is_terminal_status(Listing.Status.SOLD)


def test_transition_services_use_persisted_locked_status_not_stale_object_state():
    actor = create_user("stale-status@example.test")
    manager = create_user("stale-manager@example.test")
    grant_role(actor, ROLE_OWNER)
    grant_role(manager, ROLE_MANAGEMENT)
    listing = create_listing_for(actor, status=Listing.Status.ACTIVE)
    stale = Listing.objects.get(pk=listing.pk)

    services.withdraw_listing(actor=actor, listing=listing)
    stale.status = Listing.Status.ACTIVE

    with pytest.raises(ValidationError):
        services.suspend_listing(actor=manager, listing=stale, reason="Already withdrawn")

    listing.refresh_from_db()
    assert listing.status == Listing.Status.WITHDRAWN
