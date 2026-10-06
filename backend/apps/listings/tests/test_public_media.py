from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.exceptions import NotFound
from rest_framework.test import APIClient

from apps.listings import services
from apps.listings.models import Listing, ListingPhoto
from apps.listings.serializers import ListingPublicSerializer
from apps.localities.models import District, Locality, Region, Ward
from apps.media.models import MediaVariant
from apps.media.services import create_image_media
from apps.media.storage import get_private_media_storage, reset_in_memory_storage
from apps.properties.models import PropertyRecord
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
    email = email or f"public-media-{uuid.uuid4().hex[:10]}@example.test"
    return get_user_model().objects.create_user(
        email=email,
        phone=f"+2557{abs(hash(email)) % 100000000:08d}",
        full_name="Public Media User",
        password="StrongPass123!",
    )


def grant_role(user, role_code=ROLE_OWNER):
    bootstrap_canonical_roles()
    return UserRole.objects.create(user=user, role=Role.objects.get(code=role_code))


def hierarchy(prefix=None):
    prefix = prefix or f"PublicMedia{uuid.uuid4().hex[:8]}"
    region = Region.objects.create(name=f"{prefix} Region")
    district = District.objects.create(region=region, name=f"{prefix} District")
    ward = Ward.objects.create(district=district, name=f"{prefix} Ward")
    locality = Locality.objects.create(ward=ward, name=f"{prefix} Street", kind=Locality.Kind.STREET, approved=True)
    return region, district, ward, locality


def property_record(owner):
    region, district, ward, locality = hierarchy()
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
        created_by=owner,
    )


def listing(owner, *, status=Listing.Status.ACTIVE, prop=None):
    return Listing.objects.create(
        listing_id=f"LST-{uuid.uuid4().hex[:16].upper()}",
        property=prop or property_record(owner),
        lister=owner,
        lister_kind=Listing.ListerKind.OWNER,
        selling_price=Decimal("100000000"),
        owner_price=Decimal("100000000"),
        currency=Listing.Currency.TZS,
        status=status,
        description="Public media listing.",
        features=[],
    )


def image_upload(color=(130, 100, 90)):
    output = BytesIO()
    Image.new("RGB", (32, 24), color=color).save(output, format="JPEG")
    return SimpleUploadedFile(f"public-{uuid.uuid4().hex}.jpg", output.getvalue(), content_type="image/jpeg")


def listing_media(actor, target_listing, *, color=(130, 100, 90)):
    return create_image_media(actor=actor, owner_type="listing", owner_id=target_listing.listing_id, image=image_upload(color=color))


def property_media(actor, target_property):
    return create_image_media(actor=actor, owner_type="property_record", owner_id=target_property.property_id, image=image_upload())


def add_photo(actor, target_listing, *, position=0, color=(130, 100, 90)):
    media = listing_media(actor, target_listing, color=color)
    return ListingPhoto.objects.create(listing=target_listing, media=media, position=position)


@pytest.mark.parametrize("status", [Listing.Status.ACTIVE, Listing.Status.UNDER_OFFER])
def test_public_listing_serializer_generates_display_url_for_public_statuses(status):
    actor = create_user()
    grant_role(actor)
    target = listing(actor, status=status)
    photo = add_photo(actor, target)

    data = ListingPublicSerializer(services.get_public_listing(listing_id=target.listing_id)).data
    signed = get_private_media_storage().signed_requests[-1]
    display_variant = photo.media.variants.get(kind=MediaVariant.Kind.DISPLAY)
    original_variant = photo.media.variants.get(kind=MediaVariant.Kind.ORIGINAL)

    assert data["photos"] == [{"position": 0, "url": f"signed-media:{signed['token']}:ttl:123"}]
    assert data["photos"][0]["url"].startswith("signed-media:")
    assert signed["key"] == display_variant.file_key
    assert signed["key"] != original_variant.file_key
    assert signed["expires_in"] == 123


@pytest.mark.parametrize(
    "status",
    [
        Listing.Status.DRAFT,
        Listing.Status.SOLD,
        Listing.Status.WITHDRAWN,
        Listing.Status.SUSPENDED,
    ],
)
def test_public_display_signing_denies_hidden_listing_statuses(status):
    actor = create_user()
    grant_role(actor)
    target = listing(actor, status=status)
    photo = add_photo(actor, target)

    with pytest.raises(NotFound):
        services.get_public_listing_photo_display_access(listing=target, listing_photo=photo)

    assert get_private_media_storage().signed_requests == []


def test_public_photo_response_preserves_order_and_hides_media_internals():
    actor = create_user()
    grant_role(actor)
    target = listing(actor)
    second = add_photo(actor, target, position=2, color=(100, 120, 130))
    first = add_photo(actor, target, position=0, color=(90, 120, 150))

    data = ListingPublicSerializer(services.get_public_listing(listing_id=target.listing_id)).data
    rendered = repr(data).lower()

    assert [photo["position"] for photo in data["photos"]] == [0, 2]
    assert len(get_private_media_storage().signed_requests) == 2
    assert get_private_media_storage().signed_requests[0]["key"] == first.media.variants.get(kind=MediaVariant.Kind.DISPLAY).file_key
    assert get_private_media_storage().signed_requests[1]["key"] == second.media.variants.get(kind=MediaVariant.Kind.DISPLAY).file_key
    for forbidden in [
        "file_key",
        "file_hash",
        "original",
        "captured_location",
        "captured_at",
        "device",
        "uploaded_by",
        "object_id",
        "content_type",
        "owner_price",
        "pin",
        "boundary",
        "coordinates",
    ]:
        assert forbidden not in rendered


def test_cross_listing_photo_rejected():
    actor = create_user()
    grant_role(actor)
    first = listing(actor)
    second = listing(actor)
    second_photo = add_photo(actor, second)

    with pytest.raises(NotFound):
        services.get_public_listing_photo_display_access(listing=first, listing_photo=second_photo)

    assert get_private_media_storage().signed_requests == []


def test_property_owned_media_and_unassociated_media_are_rejected():
    actor = create_user()
    grant_role(actor)
    target = listing(actor)
    wrong_media = property_media(actor, target.property)
    malicious_photo = ListingPhoto.objects.create(listing=target, media=wrong_media, position=0)
    unassociated_media = listing_media(actor, target)

    with pytest.raises(NotFound):
        services.get_public_listing_photo_display_access(listing=target, listing_photo=malicious_photo)
    with pytest.raises(NotFound):
        services.get_public_listing_photo_display_access(listing=target, listing_photo=unassociated_media.media_id)

    assert get_private_media_storage().signed_requests == []


def test_missing_display_variant_fails_safely_and_is_omitted_from_serializer():
    actor = create_user()
    grant_role(actor)
    target = listing(actor)
    photo = add_photo(actor, target)
    photo.media.variants.filter(kind=MediaVariant.Kind.DISPLAY).delete()

    with pytest.raises(NotFound):
        services.get_public_listing_photo_display_access(listing=target, listing_photo=photo)

    data = ListingPublicSerializer(services.get_public_listing(listing_id=target.listing_id)).data

    assert data["photos"] == []
    assert get_private_media_storage().signed_requests == []


def test_storage_signing_failure_fails_safely_without_falling_back_to_original():
    class FailingStorage:
        def generate_signed_read_url(self, *, key, expires_in=None):
            raise RuntimeError("backend credentials unavailable")

    actor = create_user()
    grant_role(actor)
    target = listing(actor)
    photo = add_photo(actor, target)

    with patch("apps.listings.services.get_private_media_storage", return_value=FailingStorage()):
        with pytest.raises(NotFound):
            services.get_public_listing_photo_display_access(listing=target, listing_photo=photo)
        data = ListingPublicSerializer(services.get_public_listing(listing_id=target.listing_id)).data

    assert data["photos"] == []


def test_private_media_access_endpoint_still_requires_authentication():
    actor = create_user()
    grant_role(actor)
    target = listing(actor)
    photo = add_photo(actor, target)

    response = APIClient().get(f"/api/v1/media/{photo.media.media_id}/access/")

    assert response.status_code == 401
