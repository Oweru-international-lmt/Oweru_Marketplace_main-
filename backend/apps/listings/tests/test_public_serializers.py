from decimal import Decimal
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import Point, Polygon
from django.utils import timezone

from apps.lister_identity.models import ListerIdentity
from apps.listings.models import Listing, ListingPhoto
from apps.listings.serializers import ListingPrivateSerializer, ListingPublicSerializer, PropertyRecordPublicSerializer
from apps.localities.models import District, Locality, Region, Ward
from apps.media.models import Media, MediaVariant
from apps.properties.duplicate_services import record_possible_duplicate
from apps.properties.models import PossibleDuplicate, PropertyRecord
from apps.roles.catalog import ROLE_OWNER
from apps.roles.models import Role, UserRole
from apps.roles.services import bootstrap_canonical_roles


pytestmark = pytest.mark.django_db


def create_user(email=None):
    email = email or f"public-serializer-{uuid.uuid4().hex[:10]}@example.test"
    return get_user_model().objects.create_user(
        email=email,
        phone=f"+2557{abs(hash(email)) % 100000000:08d}",
        full_name="Public Serializer User",
        password="StrongPass123!",
    )


def grant_role(user, role_code=ROLE_OWNER):
    bootstrap_canonical_roles()
    return UserRole.objects.create(user=user, role=Role.objects.get(code=role_code))


def create_hierarchy(prefix=None):
    prefix = prefix or f"PublicSerializer{uuid.uuid4().hex[:8]}"
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


def create_property_record(*, created_by=None, with_boundary=True):
    region, district, ward, locality = create_hierarchy()
    boundary = None
    if with_boundary:
        boundary = Polygon(
            (
                (39.2000, -6.7900),
                (39.2100, -6.7900),
                (39.2100, -6.7800),
                (39.2000, -6.7900),
            ),
            srid=4326,
        )
    return PropertyRecord.objects.create(
        property_id=f"OWR-{uuid.uuid4().hex[:16].upper()}",
        category=PropertyRecord.Category.LAND,
        pin=Point(39.2083, -6.7924, srid=4326),
        boundary=boundary,
        region=region,
        district=district,
        ward=ward,
        locality=locality,
        stated_size=Decimal("1200.50"),
        size_unit="sqm",
        title_type=PropertyRecord.TitleType.UNKNOWN,
        created_by=created_by or create_user(),
    )


def create_listing(*, lister=None, property_record=None, status=Listing.Status.ACTIVE, lister_kind=Listing.ListerKind.OWNER):
    lister = lister or create_user()
    property_record = property_record or create_property_record(created_by=lister)
    selling_price = Decimal("100000000")
    owner_price = selling_price if lister_kind == Listing.ListerKind.OWNER else Decimal("95000000")
    return Listing.objects.create(
        listing_id=f"LST-{uuid.uuid4().hex[:16].upper()}",
        property=property_record,
        lister=lister,
        lister_kind=lister_kind,
        selling_price=selling_price,
        owner_price=owner_price,
        currency=Listing.Currency.TZS,
        status=status,
        description="Public-safe serializer listing.",
        features=["road access", "surveyed"],
    )


def create_verified_identity(user):
    return ListerIdentity.objects.create(
        user=user,
        national_id_number=f"NIDA-{uuid.uuid4().hex[:12]}",
        national_id_photo_ref="private/id-photo.jpg",
        live_selfie_ref="private/selfie.jpg",
        status=ListerIdentity.Status.APPROVED,
        reviewed_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(days=30),
    )


def attach_private_media(listing):
    content_type = ContentType.objects.get_for_model(Listing)
    media = Media.objects.create(
        content_type=content_type,
        object_id=listing.pk,
        uploaded_by=listing.lister,
        file_key="private/original-listing-photo.jpg",
        source=Media.Source.UPLOAD,
        captured_at=timezone.now(),
        captured_location=Point(39.2083, -6.7924, srid=4326),
        device="Sensitive Camera",
        file_hash="a" * 64,
        mime_type="image/jpeg",
        size_bytes=1000,
    )
    MediaVariant.objects.create(
        media=media,
        kind=MediaVariant.Kind.ORIGINAL,
        file_key="private/original-variant.jpg",
        mime_type="image/jpeg",
        size_bytes=1000,
        width=1024,
        height=768,
    )
    MediaVariant.objects.create(
        media=media,
        kind=MediaVariant.Kind.DISPLAY,
        file_key="private/display-variant.jpg",
        mime_type="image/jpeg",
        size_bytes=500,
        width=800,
        height=600,
    )
    ListingPhoto.objects.create(listing=listing, media=media, position=0)
    return media


def nested_keys(value):
    keys = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            keys.add(str(key))
            keys.update(nested_keys(nested))
    elif isinstance(value, list):
        for item in value:
            keys.update(nested_keys(item))
    return keys


def test_public_listing_serializer_exposes_only_expected_safe_shape():
    lister = create_user()
    grant_role(lister)
    create_verified_identity(lister)
    listing = create_listing(lister=lister, lister_kind=Listing.ListerKind.AGENT)

    data = ListingPublicSerializer(listing).data

    assert set(data) == {
        "listing_id",
        "selling_price",
        "currency",
        "status",
        "description",
        "features",
        "created_at",
        "property",
        "lister",
        "photos",
    }
    assert data["listing_id"] == listing.listing_id
    assert data["selling_price"] == "100000000"
    assert data["currency"] == Listing.Currency.TZS
    assert data["status"] == Listing.Status.ACTIVE
    assert data["description"] == listing.description
    assert data["features"] == listing.features


def test_public_property_serializer_exposes_safe_property_and_locality_facts():
    property_record = create_property_record()

    data = PropertyRecordPublicSerializer(property_record).data

    assert set(data) == {"property_id", "category", "stated_size", "size_unit", "title_type", "location"}
    assert data["property_id"] == property_record.property_id
    assert data["category"] == property_record.category
    assert data["stated_size"] == "1200.50"
    assert data["size_unit"] == "sqm"
    assert data["title_type"] == property_record.title_type
    assert data["location"] == {
        "region": property_record.region.name,
        "district": property_record.district.name,
        "ward": property_record.ward.name,
        "locality": property_record.locality.name,
        "locality_kind": property_record.locality.kind,
    }


def test_public_lister_serializer_exposes_only_display_role_verification_and_membership():
    lister = create_user()
    grant_role(lister)
    create_verified_identity(lister)
    listing = create_listing(lister=lister)

    data = ListingPublicSerializer(listing).data["lister"]

    assert set(data) == {"display_name", "lister_kind", "verification", "member_since"}
    assert data["display_name"] == lister.full_name
    assert data["lister_kind"] == Listing.ListerKind.OWNER
    assert data["verification"] == {"level": 1, "label": "Identity verified", "is_verified": True}
    assert data["member_since"] is not None


def test_public_serializer_excludes_private_listing_property_user_identity_media_duplicate_and_rbac_data():
    lister = create_user()
    grant_role(lister)
    create_verified_identity(lister)
    listing = create_listing(lister=lister)
    attach_private_media(listing)
    duplicate_property = create_property_record(created_by=create_user())
    record_possible_duplicate(
        property_a=listing.property,
        property_b=duplicate_property,
        signals=[PossibleDuplicate.SIGNAL_PIN_PROXIMITY],
    )

    data = ListingPublicSerializer(listing).data
    keys = nested_keys(data)
    rendered = repr(data).lower()

    forbidden_keys = {
        "owner_price",
        "pin",
        "boundary",
        "coordinates",
        "created_by",
        "user",
        "user_id",
        "id",
        "email",
        "phone",
        "whatsapp",
        "national_id_number",
        "national_id_photo_ref",
        "live_selfie_ref",
        "reviewed_by",
        "review_reason",
        "media",
        "file_key",
        "file_hash",
        "captured_location",
        "device",
        "variants",
        "possible_duplicate",
        "signals",
        "distance_meters",
        "size_difference_percent",
        "audit",
        "roles",
        "role",
        "user_roles",
    }
    assert keys.isdisjoint(forbidden_keys)

    forbidden_values = [
        "95000000",
        "39.2083",
        "-6.7924",
        "private/id-photo.jpg",
        "private/selfie.jpg",
        "private/original-listing-photo.jpg",
        "private/original-variant.jpg",
        "private/display-variant.jpg",
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "original",
        "sensitive camera",
        lister.email,
        lister.phone,
    ]
    for value in forbidden_values:
        assert value.lower() not in rendered


def test_public_serializer_isolated_from_private_listing_serializer():
    listing = create_listing()

    public_data = ListingPublicSerializer(listing).data
    private_data = ListingPrivateSerializer(listing).data

    assert "owner_price" in private_data
    assert "owner_price" not in public_data
    assert "property_id" in private_data
    assert "property" in public_data


def test_public_serializer_exact_allowlists_guard_against_unrelated_private_model_fields():
    listing = create_listing()

    data = ListingPublicSerializer(listing).data

    assert set(data) == set(ListingPublicSerializer.Meta.fields)
    assert set(data["property"]) == set(PropertyRecordPublicSerializer.Meta.fields)
    assert set(data["property"]["location"]) == {"region", "district", "ward", "locality", "locality_kind"}
    assert set(data["lister"]) == {"display_name", "lister_kind", "verification", "member_since"}
