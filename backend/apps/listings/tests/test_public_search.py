from decimal import Decimal
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.listings.models import Listing
from apps.listings.public_search import (
    SORT_NEWEST,
    SORT_PRICE_ASC,
    SORT_PRICE_DESC,
    get_public_listing_search_queryset,
    paginate_public_listings,
)
from apps.localities.models import District, Locality, Region, Ward
from apps.properties.duplicate_services import record_possible_duplicate
from apps.properties.models import PossibleDuplicate, PropertyRecord


pytestmark = pytest.mark.django_db


def create_user(email=None):
    email = email or f"public-search-{uuid.uuid4().hex[:10]}@example.test"
    return get_user_model().objects.create_user(
        email=email,
        phone=f"+2557{abs(hash(email)) % 100000000:08d}",
        full_name="Public Search User",
        password="StrongPass123!",
    )


def hierarchy(prefix=None):
    prefix = prefix or f"PublicSearch{uuid.uuid4().hex[:8]}"
    region = Region.objects.create(name=f"{prefix} Region")
    district = District.objects.create(region=region, name=f"{prefix} District")
    ward = Ward.objects.create(district=district, name=f"{prefix} Ward")
    locality = Locality.objects.create(ward=ward, name=f"{prefix} Street", kind=Locality.Kind.STREET, approved=True)
    return region, district, ward, locality


def property_record(
    *,
    owner=None,
    category=PropertyRecord.Category.LAND,
    stated_size=Decimal("1200.00"),
    title_type=PropertyRecord.TitleType.UNKNOWN,
    location=None,
):
    region, district, ward, locality = location or hierarchy()
    return PropertyRecord.objects.create(
        property_id=f"OWR-{uuid.uuid4().hex[:16].upper()}",
        category=category,
        pin=Point(39.2083, -6.7924, srid=4326),
        boundary=None,
        region=region,
        district=district,
        ward=ward,
        locality=locality,
        stated_size=stated_size,
        size_unit="sqm",
        title_type=title_type,
        created_by=owner or create_user(),
    )


def listing(
    *,
    owner=None,
    status=Listing.Status.ACTIVE,
    prop=None,
    selling_price=Decimal("100000000"),
    owner_price=None,
    lister_kind=Listing.ListerKind.OWNER,
    listing_uuid=None,
):
    owner = owner or create_user()
    prop = prop or property_record(owner=owner)
    if owner_price is None:
        owner_price = selling_price if lister_kind == Listing.ListerKind.OWNER else selling_price - Decimal("1")
    return Listing.objects.create(
        id=listing_uuid or uuid.uuid4(),
        listing_id=f"LST-{uuid.uuid4().hex[:16].upper()}",
        property=prop,
        lister=owner,
        lister_kind=lister_kind,
        selling_price=selling_price,
        owner_price=owner_price,
        currency=Listing.Currency.TZS,
        status=status,
        description="Public search listing.",
        features=[],
    )


def ids(queryset):
    return list(queryset.values_list("listing_id", flat=True))


def test_public_search_visibility_includes_only_public_statuses():
    active = listing(status=Listing.Status.ACTIVE)
    under_offer = listing(status=Listing.Status.UNDER_OFFER)
    hidden = [
        listing(status=Listing.Status.DRAFT),
        listing(status=Listing.Status.SOLD),
        listing(status=Listing.Status.WITHDRAWN),
        listing(status=Listing.Status.SUSPENDED),
    ]

    result_ids = set(ids(get_public_listing_search_queryset()))

    assert active.listing_id in result_ids
    assert under_offer.listing_id in result_ids
    assert result_ids.isdisjoint({item.listing_id for item in hidden})


def test_category_filter_and_invalid_category_validation():
    land = listing(prop=property_record(category=PropertyRecord.Category.LAND))
    listing(prop=property_record(category=PropertyRecord.Category.HOUSE))

    assert ids(get_public_listing_search_queryset({"category": PropertyRecord.Category.LAND})) == [land.listing_id]
    with pytest.raises(ValidationError):
        get_public_listing_search_queryset({"category": "PALACE"})


def test_location_filters_use_region_district_and_ward_ids():
    first_location = hierarchy("FirstLocation")
    second_location = hierarchy("SecondLocation")
    first = listing(prop=property_record(location=first_location))
    listing(prop=property_record(location=second_location))
    region, district, ward, _locality = first_location

    assert ids(get_public_listing_search_queryset({"region": str(region.pk)})) == [first.listing_id]
    assert ids(get_public_listing_search_queryset({"district": str(district.pk)})) == [first.listing_id]
    assert ids(get_public_listing_search_queryset({"ward": str(ward.pk)})) == [first.listing_id]


def test_price_filters_use_selling_price_and_reject_invalid_ranges():
    low = listing(selling_price=Decimal("100"))
    mid = listing(selling_price=Decimal("200"))
    high = listing(selling_price=Decimal("300"))

    assert set(ids(get_public_listing_search_queryset({"min_price": "200"}))) == {mid.listing_id, high.listing_id}
    assert set(ids(get_public_listing_search_queryset({"max_price": "200"}))) == {low.listing_id, mid.listing_id}
    assert ids(get_public_listing_search_queryset({"min_price": "150", "max_price": "250"})) == [mid.listing_id]
    with pytest.raises(ValidationError):
        get_public_listing_search_queryset({"min_price": "250", "max_price": "150"})
    with pytest.raises(ValidationError):
        get_public_listing_search_queryset({"min_price": "not-a-number"})


def test_owner_price_has_no_effect_on_public_price_filtering():
    agent = listing(
        selling_price=Decimal("100"),
        owner_price=Decimal("1"),
        lister_kind=Listing.ListerKind.AGENT,
    )

    assert agent not in list(get_public_listing_search_queryset({"max_price": "10"}))


def test_size_filters_and_invalid_size_validation():
    small = listing(prop=property_record(stated_size=Decimal("500.00")))
    medium = listing(prop=property_record(stated_size=Decimal("1000.00")))
    large = listing(prop=property_record(stated_size=Decimal("1500.00")))

    assert set(ids(get_public_listing_search_queryset({"min_size": "1000"}))) == {medium.listing_id, large.listing_id}
    assert set(ids(get_public_listing_search_queryset({"max_size": "1000"}))) == {small.listing_id, medium.listing_id}
    assert ids(get_public_listing_search_queryset({"min_size": "750", "max_size": "1250"})) == [medium.listing_id]
    with pytest.raises(ValidationError):
        get_public_listing_search_queryset({"min_size": "1250", "max_size": "750"})
    with pytest.raises(ValidationError):
        get_public_listing_search_queryset({"max_size": "many"})


def test_title_type_filter_and_invalid_title_type_validation():
    titled = listing(prop=property_record(title_type=PropertyRecord.TitleType.REGISTERED_TITLE))
    listing(prop=property_record(title_type=PropertyRecord.TitleType.NONE))

    assert ids(get_public_listing_search_queryset({"title_type": PropertyRecord.TitleType.REGISTERED_TITLE})) == [
        titled.listing_id
    ]
    with pytest.raises(ValidationError):
        get_public_listing_search_queryset({"title_type": "MAGIC_DEED"})


def test_sorting_default_newest_explicit_newest_price_and_deterministic_tie_breakers():
    older = listing(selling_price=Decimal("300"))
    newer = listing(selling_price=Decimal("100"))
    tie_low = listing(selling_price=Decimal("200"), listing_uuid=uuid.UUID("00000000-0000-0000-0000-000000000001"))
    tie_high = listing(selling_price=Decimal("200"), listing_uuid=uuid.UUID("00000000-0000-0000-0000-000000000002"))
    now = timezone.now()
    Listing.objects.filter(pk=older.pk).update(created_at=now - timezone.timedelta(days=2))
    Listing.objects.filter(pk=newer.pk).update(created_at=now)
    Listing.objects.filter(pk__in=[tie_low.pk, tie_high.pk]).update(created_at=now - timezone.timedelta(days=1))

    assert ids(get_public_listing_search_queryset())[:4] == [
        newer.listing_id,
        tie_high.listing_id,
        tie_low.listing_id,
        older.listing_id,
    ]
    assert ids(get_public_listing_search_queryset({"sort": SORT_NEWEST}))[:4] == ids(get_public_listing_search_queryset())[:4]
    assert ids(get_public_listing_search_queryset({"sort": SORT_PRICE_ASC}))[:4] == [
        newer.listing_id,
        tie_high.listing_id,
        tie_low.listing_id,
        older.listing_id,
    ]
    assert ids(get_public_listing_search_queryset({"sort": SORT_PRICE_DESC}))[:4] == [
        older.listing_id,
        tie_high.listing_id,
        tie_low.listing_id,
        newer.listing_id,
    ]


def test_arbitrary_sort_and_filter_injection_are_rejected():
    with pytest.raises(ValidationError):
        get_public_listing_search_queryset({"sort": "owner_price"})
    with pytest.raises(ValidationError):
        get_public_listing_search_queryset({"order_by": "selling_price"})
    with pytest.raises(ValidationError):
        get_public_listing_search_queryset({"pin": "39.2083,-6.7924"})
    with pytest.raises(ValidationError):
        get_public_listing_search_queryset({"raw_sql": "1=1"})


def test_multiple_filters_compose_correctly():
    location = hierarchy("ComposedLocation")
    expected = listing(
        prop=property_record(
            category=PropertyRecord.Category.HOUSE,
            stated_size=Decimal("800.00"),
            title_type=PropertyRecord.TitleType.CCRO,
            location=location,
        ),
        selling_price=Decimal("250"),
    )
    listing(prop=property_record(category=PropertyRecord.Category.HOUSE, stated_size=Decimal("800.00"), location=location), selling_price=Decimal("500"))
    listing(prop=property_record(category=PropertyRecord.Category.LAND, stated_size=Decimal("800.00"), location=location), selling_price=Decimal("250"))
    region, _district, _ward, _locality = location

    result = get_public_listing_search_queryset({
        "category": PropertyRecord.Category.HOUSE,
        "region": str(region.pk),
        "min_price": "200",
        "max_price": "300",
        "min_size": "700",
        "max_size": "900",
        "title_type": PropertyRecord.TitleType.CCRO,
    })

    assert ids(result) == [expected.listing_id]


def test_pagination_defaults_custom_bounds_and_stable_pages():
    with override_settings(PUBLIC_LISTING_PAGE_SIZE=2, PUBLIC_LISTING_MAX_PAGE_SIZE=3):
        created = [listing() for _ in range(5)]
        now = timezone.now()
        for index, item in enumerate(created):
            Listing.objects.filter(pk=item.pk).update(created_at=now - timezone.timedelta(minutes=index))
        queryset = get_public_listing_search_queryset()

        first_page = paginate_public_listings(queryset).as_dict()
        second_page = paginate_public_listings(queryset, {"page": 2}).as_dict()
        custom_page = paginate_public_listings(queryset, {"page_size": 3}).as_dict()

        assert first_page["count"] == 5
        assert first_page["next"] == 2
        assert first_page["previous"] is None
        assert len(first_page["results"]) == 2
        assert second_page["previous"] == 1
        assert len(custom_page["results"]) == 3
        assert [item.pk for item in first_page["results"] + second_page["results"]] == [
            item.pk for item in list(queryset[:4])
        ]
        with pytest.raises(ValidationError):
            paginate_public_listings(queryset, {"page_size": 4})
        with pytest.raises(ValidationError):
            paginate_public_listings(queryset, {"page_size": "huge"})


def test_duplicate_state_and_private_media_absence_do_not_affect_public_search():
    first = listing()
    second = listing()
    record_possible_duplicate(
        property_a=first.property,
        property_b=second.property,
        signals=[PossibleDuplicate.SIGNAL_PIN_PROXIMITY],
    )

    result_ids = set(ids(get_public_listing_search_queryset()))

    assert first.listing_id in result_ids
    assert second.listing_id in result_ids
