from datetime import timedelta
from decimal import Decimal
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.listings import services
from apps.listings.models import Listing
from apps.localities.models import District, Locality, Region, Ward
from apps.properties.duplicate_services import confirm_possible_duplicate, record_possible_duplicate
from apps.properties.models import PossibleDuplicate, PropertyRecord
from apps.roles.catalog import ROLE_MANAGEMENT, ROLE_OWNER
from apps.roles.models import Role, UserRole
from apps.roles.services import bootstrap_canonical_roles


pytestmark = pytest.mark.django_db


def create_user(email=None, *, is_active=True):
    email = email or f"public-listing-{uuid.uuid4().hex[:10]}@example.test"
    return get_user_model().objects.create_user(
        email=email,
        phone=f"+2557{abs(hash(email)) % 100000000:08d}",
        full_name="Public Listing User",
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
    prefix = prefix or f"PublicListing{uuid.uuid4().hex[:8]}"
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
    prefix = prefix or f"PublicProp{uuid.uuid4().hex[:8]}"
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


def create_listing(*, lister=None, status=Listing.Status.DRAFT, property_record=None, **overrides):
    lister = lister or create_user()
    property_record = property_record or create_property_record(created_by=lister)
    attrs = {
        "listing_id": f"LST-{uuid.uuid4().hex[:16].upper()}",
        "property": property_record,
        "lister": lister,
        "lister_kind": Listing.ListerKind.OWNER,
        "selling_price": Decimal("100000000"),
        "owner_price": Decimal("100000000"),
        "currency": Listing.Currency.TZS,
        "status": status,
        "description": "Public listing visibility test.",
        "features": ["road access"],
    }
    attrs.update(overrides)
    return Listing.objects.create(**attrs)


def public_not_found_detail(listing_id):
    with pytest.raises(NotFound) as exc:
        services.get_public_listing(listing_id=listing_id)
    return str(exc.value.detail)


def test_public_listing_queryset_includes_only_active_and_under_offer_statuses():
    visible_active = create_listing(status=Listing.Status.ACTIVE)
    visible_under_offer = create_listing(status=Listing.Status.UNDER_OFFER)
    hidden = [
        create_listing(status=Listing.Status.DRAFT),
        create_listing(status=Listing.Status.SOLD),
        create_listing(status=Listing.Status.WITHDRAWN),
        create_listing(status=Listing.Status.SUSPENDED),
    ]

    listing_ids = set(services.get_public_listings().values_list("listing_id", flat=True))

    assert visible_active.listing_id in listing_ids
    assert visible_under_offer.listing_id in listing_ids
    assert listing_ids.isdisjoint({listing.listing_id for listing in hidden})


def test_public_listing_queryset_uses_deterministic_newest_first_ordering():
    older = create_listing(status=Listing.Status.ACTIVE)
    newer = create_listing(status=Listing.Status.ACTIVE)
    Listing.objects.filter(pk=older.pk).update(created_at=timezone.now() - timedelta(days=1))
    Listing.objects.filter(pk=newer.pk).update(created_at=timezone.now())

    listing_ids = list(services.get_public_listings().values_list("listing_id", flat=True))

    assert listing_ids.index(newer.listing_id) < listing_ids.index(older.listing_id)


@pytest.mark.parametrize("status", [Listing.Status.ACTIVE, Listing.Status.UNDER_OFFER])
def test_get_public_listing_returns_public_statuses(status):
    listing = create_listing(status=status)

    assert services.get_public_listing(listing_id=listing.listing_id) == listing


@pytest.mark.parametrize(
    "status",
    [
        Listing.Status.DRAFT,
        Listing.Status.SOLD,
        Listing.Status.WITHDRAWN,
        Listing.Status.SUSPENDED,
    ],
)
def test_get_public_listing_hides_non_public_statuses_like_missing_listings(status):
    listing = create_listing(status=status)
    hidden_detail = public_not_found_detail(listing.listing_id)
    missing_detail = public_not_found_detail("LST-DOES-NOT-EXIST")

    assert hidden_detail == missing_detail


def test_possible_duplicate_review_status_does_not_affect_public_listing_visibility():
    manager = create_user()
    grant_role(manager, ROLE_MANAGEMENT)
    listing = create_listing(status=Listing.Status.ACTIVE)
    other_property = create_property_record(created_by=create_user())
    candidate = record_possible_duplicate(
        property_a=listing.property,
        property_b=other_property,
        signals=[PossibleDuplicate.SIGNAL_PIN_PROXIMITY],
    )

    assert services.get_public_listing(listing_id=listing.listing_id) == listing

    confirm_possible_duplicate(actor=manager, possible_duplicate=candidate)

    assert services.get_public_listing(listing_id=listing.listing_id) == listing


def test_public_listing_visibility_does_not_require_authentication_or_current_lister_role():
    lister = create_user()
    assignment = grant_role(lister, ROLE_OWNER)
    listing = create_listing(lister=lister, status=Listing.Status.ACTIVE)
    assignment.is_active = False
    assignment.save(update_fields=["is_active"])

    assert services.get_public_listing(listing_id=listing.listing_id) == listing


def test_public_listing_queryset_selects_single_valued_relations_for_public_composition():
    create_listing(status=Listing.Status.ACTIVE)
    create_listing(status=Listing.Status.ACTIVE)

    with CaptureQueriesContext(connection) as captured:
        listings = list(services.get_public_listings())
        for listing in listings:
            assert listing.property.region.name
            assert listing.property.district.name
            assert listing.property.ward.name
            assert listing.property.locality.name
            assert listing.lister.full_name
            assert list(listing.public_photos) == []

    assert len(captured) == 2


def test_activation_remains_fail_closed_while_phone_confirmation_is_unavailable():
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    listing = create_listing(lister=actor, status=Listing.Status.DRAFT)

    requirements = {item.code: item.status for item in services.check_listing_activation_eligibility(listing=listing).requirements}

    assert requirements["lister_phone_confirmed"] == "UNAVAILABLE"
    with pytest.raises(ValidationError) as exc:
        services.activate_listing(actor=actor, listing=listing)
    assert "lister_phone_confirmed" in exc.value.detail["activation"]
