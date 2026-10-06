from decimal import Decimal
from io import BytesIO
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.listings.models import Listing, ListingPhoto
from apps.localities.models import District, Locality, Region, Ward
from apps.media.models import MediaVariant
from apps.media.services import create_image_media
from apps.media.storage import get_private_media_storage, reset_in_memory_storage
from apps.properties.duplicate_services import record_possible_duplicate
from apps.properties.models import PossibleDuplicate, PropertyRecord
from apps.roles.catalog import ROLE_OWNER
from apps.roles.models import Role, UserRole
from apps.roles.services import bootstrap_canonical_roles


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def media_settings():
    reset_in_memory_storage()
    with override_settings(
        MEDIA_STORAGE_BACKEND="memory",
        MEDIA_MAX_UPLOAD_BYTES=1024 * 1024,
        MEDIA_ALLOWED_IMAGE_MIME_TYPES=["image/jpeg", "image/png", "image/webp"],
        MEDIA_MAX_IMAGE_WIDTH=80,
        MEDIA_MAX_IMAGE_HEIGHT=60,
        MEDIA_SIGNED_URL_TTL_SECONDS=123,
    ):
        yield
    reset_in_memory_storage()


def create_user(email=None):
    email = email or f"public-api-{uuid.uuid4().hex[:10]}@example.test"
    return get_user_model().objects.create_user(
        email=email,
        phone=f"+2557{abs(hash(email)) % 100000000:08d}",
        full_name="Public API User",
        password="StrongPass123!",
    )


def grant_role(user, role_code=ROLE_OWNER):
    bootstrap_canonical_roles()
    return UserRole.objects.create(user=user, role=Role.objects.get(code=role_code))


def hierarchy(prefix=None):
    prefix = prefix or f"PublicApi{uuid.uuid4().hex[:8]}"
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
):
    owner = owner or create_user()
    prop = prop or property_record(owner=owner)
    if owner_price is None:
        owner_price = selling_price if lister_kind == Listing.ListerKind.OWNER else selling_price - Decimal("1")
    return Listing.objects.create(
        listing_id=f"LST-{uuid.uuid4().hex[:16].upper()}",
        property=prop,
        lister=owner,
        lister_kind=lister_kind,
        selling_price=selling_price,
        owner_price=owner_price,
        currency=Listing.Currency.TZS,
        status=status,
        description="Public API listing.",
        features=["road access"],
    )


def image_upload(color=(130, 100, 90)):
    output = BytesIO()
    Image.new("RGB", (32, 24), color=color).save(output, format="JPEG")
    return SimpleUploadedFile(f"public-api-{uuid.uuid4().hex}.jpg", output.getvalue(), content_type="image/jpeg")


def listing_media(actor, target_listing, *, color=(130, 100, 90)):
    return create_image_media(actor=actor, owner_type="listing", owner_id=target_listing.listing_id, image=image_upload(color=color))


def add_photo(actor, target_listing, *, position=0, color=(130, 100, 90)):
    media = listing_media(actor, target_listing, color=color)
    return ListingPhoto.objects.create(listing=target_listing, media=media, position=position)


def result_ids(response):
    return [item["listing_id"] for item in response.data["results"]]


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


def test_anonymous_search_and_detail_for_public_statuses():
    active = listing(status=Listing.Status.ACTIVE)
    under_offer = listing(status=Listing.Status.UNDER_OFFER)
    client = APIClient()

    search = client.get("/api/v1/public/listings/")
    active_detail = client.get(f"/api/v1/public/listings/{active.listing_id}/")
    under_offer_detail = client.get(f"/api/v1/public/listings/{under_offer.listing_id}/")

    assert search.status_code == 200
    assert active.listing_id in result_ids(search)
    assert under_offer.listing_id in result_ids(search)
    assert active_detail.status_code == 200
    assert under_offer_detail.status_code == 200


def test_public_search_visibility_and_hidden_detail_enumeration():
    visible = listing(status=Listing.Status.ACTIVE)
    hidden = [
        listing(status=Listing.Status.DRAFT),
        listing(status=Listing.Status.SOLD),
        listing(status=Listing.Status.WITHDRAWN),
        listing(status=Listing.Status.SUSPENDED),
    ]
    client = APIClient()

    search = client.get("/api/v1/public/listings/")
    missing = client.get("/api/v1/public/listings/LST-DOES-NOT-EXIST/")

    assert visible.listing_id in result_ids(search)
    assert set(result_ids(search)).isdisjoint({item.listing_id for item in hidden})
    for item in hidden:
        response = client.get(f"/api/v1/public/listings/{item.listing_id}/")
        assert response.status_code == 404
        assert response.data == missing.data
    assert missing.status_code == 404


def test_public_search_filters_and_combined_filters():
    location = hierarchy("PublicApiFilter")
    region, district, ward, _locality = location
    expected = listing(
        prop=property_record(
            category=PropertyRecord.Category.HOUSE,
            stated_size=Decimal("900.00"),
            title_type=PropertyRecord.TitleType.CCRO,
            location=location,
        ),
        selling_price=Decimal("250"),
    )
    listing(prop=property_record(category=PropertyRecord.Category.LAND, stated_size=Decimal("900.00"), location=location), selling_price=Decimal("250"))
    listing(prop=property_record(category=PropertyRecord.Category.HOUSE, stated_size=Decimal("2000.00"), location=location), selling_price=Decimal("500"))

    response = APIClient().get(
        "/api/v1/public/listings/",
        {
            "category": PropertyRecord.Category.HOUSE,
            "region": str(region.pk),
            "district": str(district.pk),
            "ward": str(ward.pk),
            "min_price": "200",
            "max_price": "300",
            "min_size": "800",
            "max_size": "1000",
            "title_type": PropertyRecord.TitleType.CCRO,
        },
    )

    assert response.status_code == 200
    assert result_ids(response) == [expected.listing_id]


def test_public_search_sorting_options():
    low = listing(selling_price=Decimal("100"))
    high = listing(selling_price=Decimal("300"))
    newest = listing(selling_price=Decimal("200"))
    now = timezone.now()
    Listing.objects.filter(pk=low.pk).update(created_at=now - timezone.timedelta(days=2))
    Listing.objects.filter(pk=high.pk).update(created_at=now - timezone.timedelta(days=1))
    Listing.objects.filter(pk=newest.pk).update(created_at=now)
    client = APIClient()

    assert result_ids(client.get("/api/v1/public/listings/", {"sort": "NEWEST"}))[:3] == [
        newest.listing_id,
        high.listing_id,
        low.listing_id,
    ]
    assert result_ids(client.get("/api/v1/public/listings/", {"sort": "PRICE_ASC"}))[:3] == [
        low.listing_id,
        newest.listing_id,
        high.listing_id,
    ]
    assert result_ids(client.get("/api/v1/public/listings/", {"sort": "PRICE_DESC"}))[:3] == [
        high.listing_id,
        newest.listing_id,
        low.listing_id,
    ]


def test_public_search_pagination_shape_defaults_custom_size_and_bounds():
    with override_settings(PUBLIC_LISTING_PAGE_SIZE=2, PUBLIC_LISTING_MAX_PAGE_SIZE=3):
        created = [listing() for _ in range(5)]
        now = timezone.now()
        for index, item in enumerate(created):
            Listing.objects.filter(pk=item.pk).update(created_at=now - timezone.timedelta(minutes=index))
        client = APIClient()

        default_page = client.get("/api/v1/public/listings/")
        second_page = client.get("/api/v1/public/listings/", {"page": 2})
        custom_page = client.get("/api/v1/public/listings/", {"page_size": 3})
        too_large = client.get("/api/v1/public/listings/", {"page_size": 4})
        invalid_page = client.get("/api/v1/public/listings/", {"page": 99})

    assert set(default_page.data) == {"count", "next", "previous", "results"}
    assert default_page.data["count"] == 5
    assert default_page.data["next"] == 2
    assert default_page.data["previous"] is None
    assert len(default_page.data["results"]) == 2
    assert second_page.data["previous"] == 1
    assert len(custom_page.data["results"]) == 3
    assert too_large.status_code == 400
    assert invalid_page.status_code == 404


@pytest.mark.parametrize(
    "params",
    [
        {"category": "PALACE"},
        {"title_type": "MAGIC_DEED"},
        {"min_price": "cheap"},
        {"min_size": "large"},
        {"min_price": "300", "max_price": "200"},
        {"min_size": "300", "max_size": "200"},
        {"sort": "owner_price"},
        {"unknown": "value"},
    ],
)
def test_public_search_invalid_input_returns_400(params):
    response = APIClient().get("/api/v1/public/listings/", params)

    assert response.status_code == 400


def test_public_response_privacy_and_owner_price_private_regression():
    owner = create_user()
    grant_role(owner)
    public_listing = listing(
        owner=owner,
        selling_price=Decimal("100000000"),
        owner_price=Decimal("90000000"),
        lister_kind=Listing.ListerKind.AGENT,
    )
    other = listing()
    record_possible_duplicate(
        property_a=public_listing.property,
        property_b=other.property,
        signals=[PossibleDuplicate.SIGNAL_PIN_PROXIMITY],
    )
    public_response = APIClient().get(f"/api/v1/public/listings/{public_listing.listing_id}/")
    private_client = APIClient()
    private_client.force_authenticate(owner)
    private_response = private_client.get(f"/api/v1/listings/{public_listing.listing_id}/")

    assert public_response.status_code == 200
    assert private_response.status_code == 200
    assert "owner_price" in private_response.data

    keys = nested_keys(public_response.data)
    rendered = repr(public_response.data).lower()
    forbidden_keys = {
        "owner_price",
        "pin",
        "boundary",
        "coordinates",
        "email",
        "phone",
        "whatsapp",
        "national_id_number",
        "national_id_photo_ref",
        "live_selfie_ref",
        "possible_duplicate",
        "signals",
        "reviewer",
        "roles",
        "role",
        "file_key",
        "file_hash",
        "original",
        "audit",
    }
    assert keys.isdisjoint(forbidden_keys)
    for forbidden in ["90000000", "39.2083", "-6.7924", owner.email, owner.phone, "pin_proximity"]:
        assert forbidden not in rendered


def test_public_photos_return_ordered_display_signed_urls_and_omit_unavailable_display():
    owner = create_user()
    grant_role(owner)
    target = listing(owner=owner)
    second = add_photo(owner, target, position=2, color=(130, 90, 90))
    first = add_photo(owner, target, position=0, color=(90, 130, 90))
    second.media.variants.filter(kind=MediaVariant.Kind.DISPLAY).delete()

    response = APIClient().get(f"/api/v1/public/listings/{target.listing_id}/")
    signed = get_private_media_storage().signed_requests

    assert response.status_code == 200
    assert response.data["photos"] == [{"position": 0, "url": f"signed-media:{signed[0]['token']}:ttl:123"}]
    assert signed[0]["key"] == first.media.variants.get(kind=MediaVariant.Kind.DISPLAY).file_key
    assert "original" not in repr(response.data).lower()


def test_public_endpoints_are_read_only():
    target = listing()
    client = APIClient()

    assert client.post("/api/v1/public/listings/", {}).status_code == 405
    assert client.put(f"/api/v1/public/listings/{target.listing_id}/", {}).status_code == 405
    assert client.patch(f"/api/v1/public/listings/{target.listing_id}/", {}).status_code == 405
    assert client.delete(f"/api/v1/public/listings/{target.listing_id}/").status_code == 405


def test_private_routes_remain_authenticated():
    owner = create_user()
    grant_role(owner)
    target = listing(owner=owner)
    photo = add_photo(owner, target)
    client = APIClient()

    assert client.get("/api/v1/listings/").status_code == 401
    assert client.get(f"/api/v1/listings/{target.listing_id}/").status_code == 401
    assert client.get(f"/api/v1/media/{photo.media.media_id}/access/").status_code == 401


def test_openapi_schema_contains_public_listing_paths():
    response = APIClient().get("/api/v1/schema/?format=json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/public/listings/" in paths
    assert "/api/v1/public/listings/{listing_id}/" in paths
    assert "get" in paths["/api/v1/public/listings/"]
    assert "get" in paths["/api/v1/public/listings/{listing_id}/"]
