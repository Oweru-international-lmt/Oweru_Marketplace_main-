from decimal import Decimal
import importlib.util
import uuid

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.db.models.deletion import PROTECT, ProtectedError

from apps.listings.models import Listing
from apps.localities.models import District, Locality, Region, Ward
from apps.properties.models import PropertyRecord


pytestmark = pytest.mark.django_db


def create_user(email=None):
    email = email or f"listing-lister-{uuid.uuid4().hex[:10]}@example.test"
    return get_user_model().objects.create_user(
        email=email,
        phone=f"+255{abs(hash(email)) % 1000000000:09d}",
        full_name="Listing Lister",
        password="StrongPass123!",
    )


def create_property_record(prefix=None, *, created_by=None):
    prefix = prefix or f"ListingProperty{uuid.uuid4().hex[:8]}"
    region = Region.objects.create(name=f"{prefix} Region")
    district = District.objects.create(region=region, name=f"{prefix} District")
    ward = Ward.objects.create(district=district, name=f"{prefix} Ward")
    locality = Locality.objects.create(ward=ward, name=f"{prefix} Street", kind=Locality.Kind.STREET, approved=True)
    return PropertyRecord.objects.create(
        property_id=f"PROP-{prefix.upper()}",
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
        created_by=created_by or create_user(f"{prefix.lower()}-creator@example.test"),
    )


def listing_attrs(**overrides):
    attrs = {
        "listing_id": f"LST-{uuid.uuid4().hex[:12].upper()}",
        "property": create_property_record(),
        "lister": create_user(),
        "lister_kind": Listing.ListerKind.OWNER,
        "selling_price": Decimal("100000000"),
        "owner_price": Decimal("100000000"),
        "currency": Listing.Currency.TZS,
        "description": "Near main road with clear access.",
        "features": ["road access", "surveyed"],
    }
    attrs.update(overrides)
    return attrs


def build_listing(**overrides):
    return Listing(**listing_attrs(**overrides))


def create_listing(**overrides):
    return Listing.objects.create(**listing_attrs(**overrides))


def test_listings_app_loads_and_app_labels_are_unique():
    labels = [config.label for config in apps.get_app_configs()]

    assert apps.get_app_config("listings").name == "apps.listings"
    assert len(labels) == len(set(labels))


def test_listing_references_property_record_and_lister_user():
    lister = create_user("listing-owner@example.test")
    property_record = create_property_record("Relationship", created_by=lister)

    listing = create_listing(property=property_record, lister=lister)

    assert isinstance(listing.pk, uuid.UUID)
    assert listing.property == property_record
    assert listing.lister == lister
    assert property_record.listings.get() == listing
    assert lister.listings.get() == listing
    assert listing.created_at is not None
    assert listing.updated_at is not None


def test_multiple_listings_can_reference_one_property_record():
    property_record = create_property_record("MultipleListings")

    first = create_listing(property=property_record, listing_id="LST-MULTI-001")
    second = create_listing(property=property_record, listing_id="LST-MULTI-002")

    assert set(property_record.listings.all()) == {first, second}


def test_property_and_lister_deletion_are_protected():
    listing = create_listing()

    property_field = Listing._meta.get_field("property")
    assert property_field.remote_field.on_delete is PROTECT
    with pytest.raises(RuntimeError):
        listing.property.delete()

    with pytest.raises(ProtectedError):
        listing.lister.delete()


@pytest.mark.parametrize("lister_kind", [Listing.ListerKind.OWNER, Listing.ListerKind.AGENT])
def test_documented_lister_kinds_are_accepted(lister_kind):
    listing = build_listing(lister_kind=lister_kind)

    listing.full_clean()


@pytest.mark.parametrize("lister_kind", ["LISTER", "BROKER", "COMPANY", "AGENCY", "PROFESSIONAL", "MANAGEMENT"])
def test_unsupported_lister_kind_rejected(lister_kind):
    listing = build_listing(lister_kind=lister_kind)

    with pytest.raises(ValidationError) as exc:
        listing.full_clean()
    assert "lister_kind" in exc.value.message_dict


def test_default_status_is_draft_and_documented_statuses_are_accepted():
    assert build_listing().status == Listing.Status.DRAFT

    for status in Listing.Status.values:
        listing = build_listing(status=status)
        listing.full_clean()


def test_unsupported_status_rejected():
    listing = build_listing(status="PUBLISHED")

    with pytest.raises(ValidationError) as exc:
        listing.full_clean()
    assert "status" in exc.value.message_dict


def test_default_currency_is_tzs_and_unsupported_currency_rejected():
    assert build_listing(currency=None).currency is None
    assert Listing().currency == Listing.Currency.TZS

    listing = build_listing(currency="USD")
    with pytest.raises(ValidationError) as exc:
        listing.full_clean()
    assert "currency" in exc.value.message_dict


@pytest.mark.parametrize("field", ["selling_price", "owner_price"])
@pytest.mark.parametrize("value", [Decimal("0"), Decimal("-1")])
def test_prices_must_be_positive(field, value):
    listing = build_listing(**{field: value})

    with pytest.raises(ValidationError) as exc:
        listing.full_clean()
    assert field in exc.value.message_dict


def test_owner_listing_requires_owner_price_to_equal_selling_price():
    valid = build_listing(
        lister_kind=Listing.ListerKind.OWNER,
        selling_price=Decimal("100000000"),
        owner_price=Decimal("100000000"),
    )
    valid.full_clean()

    invalid = build_listing(
        lister_kind=Listing.ListerKind.OWNER,
        selling_price=Decimal("100000000"),
        owner_price=Decimal("90000000"),
    )
    with pytest.raises(ValidationError) as exc:
        invalid.full_clean()
    assert "owner_price" in exc.value.message_dict


def test_agent_listing_requires_selling_price_at_least_owner_price():
    equal = build_listing(
        lister_kind=Listing.ListerKind.AGENT,
        selling_price=Decimal("100000000"),
        owner_price=Decimal("100000000"),
    )
    equal.full_clean()

    higher = build_listing(
        lister_kind=Listing.ListerKind.AGENT,
        selling_price=Decimal("120000000"),
        owner_price=Decimal("100000000"),
    )
    higher.full_clean()

    invalid = build_listing(
        lister_kind=Listing.ListerKind.AGENT,
        selling_price=Decimal("95000000"),
        owner_price=Decimal("100000000"),
    )
    with pytest.raises(ValidationError) as exc:
        invalid.full_clean()
    assert "selling_price" in exc.value.message_dict


def test_description_and_features_persist_without_taxonomy():
    listing = create_listing(description="Quiet plot near school.", features=["corner plot", {"note": "future taxonomy"}])

    listing.refresh_from_db()

    assert listing.description == "Quiet plot near school."
    assert listing.features == ["corner plot", {"note": "future taxonomy"}]


def test_listing_does_not_duplicate_property_owner_contact_media_or_verification_domains():
    field_names = {field.name for field in Listing._meta.get_fields()}
    forbidden = {
        "region",
        "district",
        "ward",
        "locality",
        "pin",
        "boundary",
        "stated_size",
        "size_unit",
        "title_type",
        "category",
        "owner_name",
        "owner_phone",
        "owner_whatsapp",
        "owner_bank_account",
        "owner_bank_name",
        "owner_confirmation_id",
        "owner_confirmed_at",
        "verification_level",
        "identity_verified",
        "phone_verified",
        "is_verified",
        "verification_status",
        "images",
        "photo_urls",
        "media",
    }

    assert forbidden.isdisjoint(field_names)
    assert "photos" in field_names


def test_listing_model_has_no_services_serializers_urls_or_legacy_imports():
    assert importlib.util.find_spec("apps.listings.services") is not None
    assert importlib.util.find_spec("apps.listings.serializers") is not None
    assert importlib.util.find_spec("apps.listings.urls") is not None

    imports = getattr(__import__("apps.listings.models", fromlist=["Listing"]), "__dict__", {})
    assert "legacy_authorization" not in imports
    assert "legacy_event_stream" not in imports
    assert "ListerIdentity" not in imports
