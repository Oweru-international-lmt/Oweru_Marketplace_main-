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
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient, APIRequestFactory

from apps.audit.models import AuditLog
from apps.lister_identity.models import ListerIdentity
from apps.listings.models import Listing
from apps.listings.services import check_listing_activation_eligibility
from apps.localities.models import District, Locality, Region, Ward
from apps.media.audit_events import MEDIA_ACCESSED, MEDIA_UPLOADED
from apps.media.models import Media, MediaVariant
from apps.media.services import create_image_media, get_media_read_url
from apps.media.storage import get_private_media_storage, reset_in_memory_storage
from apps.properties.models import PropertyRecord
from apps.roles.catalog import ROLE_AGENT, ROLE_OWNER
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


def create_user(email=None, *, is_active=True):
    email = email or f"media-user-{uuid.uuid4().hex[:10]}@example.test"
    return get_user_model().objects.create_user(
        email=email,
        phone=f"+2557{abs(hash(email)) % 100000000:08d}",
        full_name="Media User",
        password="StrongPass123!",
        is_active=is_active,
    )


def grant_role(user, role_code):
    bootstrap_canonical_roles()
    return UserRole.objects.create(user=user, role=Role.objects.get(code=role_code))


def hierarchy(prefix=None):
    prefix = prefix or f"Media{uuid.uuid4().hex[:8]}"
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


def listing(owner, *, lister_kind=Listing.ListerKind.OWNER):
    prop = property_record(owner)
    selling = Decimal("100000000")
    owner_price = selling if lister_kind == Listing.ListerKind.OWNER else Decimal("90000000")
    return Listing.objects.create(
        listing_id=f"LST-{uuid.uuid4().hex[:16].upper()}",
        property=prop,
        lister=owner,
        lister_kind=lister_kind,
        selling_price=selling,
        owner_price=owner_price,
        currency=Listing.Currency.TZS,
        status=Listing.Status.DRAFT,
        description="Draft listing.",
        features=[],
    )


def image_bytes(fmt="JPEG", size=(32, 24), *, exif=False):
    image = Image.new("RGB", size, color=(90, 120, 150))
    output = BytesIO()
    save_kwargs = {}
    if exif and fmt == "JPEG":
        exif_data = Image.Exif()
        exif_data[0x010F] = "Test Camera"
        exif_data[0x9286] = b"gps-like comment"
        save_kwargs["exif"] = exif_data
    image.save(output, format=fmt, **save_kwargs)
    return output.getvalue()


def upload(fmt="JPEG", content_type="image/jpeg", size=(32, 24), name="client-name.jpg", *, exif=False):
    return SimpleUploadedFile(name, image_bytes(fmt, size, exif=exif), content_type=content_type)


def request_for(actor):
    request = APIRequestFactory().post("/api/v1/media/images/")
    request.user = actor
    return request


@pytest.mark.parametrize(
    ("fmt", "content_type"),
    [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")],
)
def test_supported_image_upload_creates_media_variants(fmt, content_type):
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    owner_listing = listing(actor)

    media = create_image_media(
        actor=actor,
        owner_type="listing",
        owner_id=owner_listing.listing_id,
        image=upload(fmt, content_type),
        request=request_for(actor),
    )

    assert media.media_id.startswith("MED-")
    assert media.file_hash == media.file_hash.lower()
    assert len(media.file_hash) == 64
    assert media.file_key.startswith(f"originals/{media.media_id}/")
    assert media.file_key != "client-name.jpg"
    assert set(media.variants.values_list("kind", flat=True)) == {
        MediaVariant.Kind.ORIGINAL,
        MediaVariant.Kind.DISPLAY,
    }
    assert get_private_media_storage().exists(key=media.file_key)


@pytest.mark.parametrize(
    "bad_upload",
    [
        SimpleUploadedFile("empty.jpg", b"", content_type="image/jpeg"),
        SimpleUploadedFile("text.jpg", b"not an image", content_type="image/jpeg"),
        SimpleUploadedFile("corrupt.jpg", image_bytes("JPEG")[:8], content_type="image/jpeg"),
        SimpleUploadedFile("wrong.png", image_bytes("JPEG"), content_type="image/png"),
        SimpleUploadedFile("unsupported.gif", image_bytes("PNG"), content_type="image/gif"),
    ],
)
def test_invalid_uploads_are_rejected_and_store_nothing(bad_upload):
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    owner_listing = listing(actor)

    with pytest.raises(ValidationError):
        create_image_media(actor=actor, owner_type="listing", owner_id=owner_listing.listing_id, image=bad_upload)

    assert Media.objects.count() == 0
    assert get_private_media_storage().objects == {}


def test_oversized_upload_is_rejected():
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    owner_listing = listing(actor)

    with override_settings(MEDIA_MAX_UPLOAD_BYTES=10):
        with pytest.raises(ValidationError):
            create_image_media(actor=actor, owner_type="listing", owner_id=owner_listing.listing_id, image=upload())


def test_dangerous_filename_and_traversal_do_not_control_object_key():
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    owner_listing = listing(actor)

    media = create_image_media(
        actor=actor,
        owner_type="listing",
        owner_id=owner_listing.listing_id,
        image=upload(name="../../private/owned.jpg"),
    )

    assert ".." not in media.file_key
    assert "owned.jpg" not in media.file_key


def test_processing_resizes_without_upscaling_and_strips_exif():
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    large = create_image_media(actor=actor, owner_type="listing", owner_id=listing(actor).listing_id, image=upload(size=(160, 120), exif=True))
    display = large.variants.get(kind=MediaVariant.Kind.DISPLAY)

    assert (display.width, display.height) == (80, 60)
    display_bytes = get_private_media_storage().objects[display.file_key]["bytes"]
    with Image.open(BytesIO(display_bytes)) as derivative:
        assert derivative.getexif() == {}

    small = create_image_media(actor=actor, owner_type="listing", owner_id=listing(actor).listing_id, image=upload(size=(40, 20)))
    small_display = small.variants.get(kind=MediaVariant.Kind.DISPLAY)
    assert (small_display.width, small_display.height) == (40, 20)


def test_property_owner_upload_allowed_and_unrelated_user_denied():
    actor = create_user()
    prop = property_record(actor)
    unrelated = create_user()

    media = create_image_media(actor=actor, owner_type="property_record", owner_id=prop.property_id, image=upload())

    assert media.owner == prop
    with pytest.raises(PermissionDenied):
        create_image_media(actor=unrelated, owner_type="property_record", owner_id=prop.property_id, image=upload())


def test_fake_role_claims_unsupported_owner_and_inactive_user_denied():
    actor = create_user()
    owner_listing = listing(actor)
    actor.role = ROLE_OWNER
    actor.roles = [ROLE_OWNER]
    with pytest.raises(PermissionDenied):
        create_image_media(actor=actor, owner_type="listing", owner_id=owner_listing.listing_id, image=upload())

    grant_role(actor, ROLE_OWNER)
    with pytest.raises(ValidationError):
        create_image_media(actor=actor, owner_type="user", owner_id=str(actor.pk), image=upload())

    inactive = create_user(is_active=False)
    grant_role(inactive, ROLE_OWNER)
    with pytest.raises(PermissionDenied):
        create_image_media(actor=inactive, owner_type="listing", owner_id=owner_listing.listing_id, image=upload())


def test_authorized_private_access_returns_signed_url_without_file_key():
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    media = create_image_media(actor=actor, owner_type="listing", owner_id=listing(actor).listing_id, image=upload())

    response = get_media_read_url(actor=actor, media=media, variant=MediaVariant.Kind.DISPLAY, request=request_for(actor))

    assert response["media_id"] == media.media_id
    assert response["variant"] == MediaVariant.Kind.DISPLAY
    assert response["expires_in"] == 123
    assert media.file_key not in response["url"]
    assert response["url"].startswith("signed-media:")


def test_original_access_is_authorized_and_unrelated_access_denied():
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    media = create_image_media(actor=actor, owner_type="listing", owner_id=listing(actor).listing_id, image=upload())

    assert get_media_read_url(actor=actor, media=media, variant=MediaVariant.Kind.ORIGINAL)["variant"] == MediaVariant.Kind.ORIGINAL
    with pytest.raises(PermissionDenied):
        get_media_read_url(actor=create_user(), media=media, variant=MediaVariant.Kind.ORIGINAL)


def test_storage_failure_cleans_original():
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    owner_listing = listing(actor)

    class FailingStorage:
        def __init__(self):
            self.saved = []
            self.deleted = []

        def save_private_object(self, *, key, content, content_type=None):
            self.saved.append(key)
            if len(self.saved) == 2:
                raise RuntimeError("display failed")
            return key

        def delete_private_object(self, *, key):
            self.deleted.append(key)

    storage = FailingStorage()
    with patch("apps.media.services.get_private_media_storage", return_value=storage):
        with pytest.raises(RuntimeError):
            create_image_media(actor=actor, owner_type="listing", owner_id=owner_listing.listing_id, image=upload())

    assert storage.deleted == storage.saved[:1]
    assert Media.objects.count() == 0


def test_db_failure_cleans_stored_objects():
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    owner_listing = listing(actor)
    storage = get_private_media_storage()

    with patch("apps.media.models.Media.save", side_effect=RuntimeError("db failed")):
        with pytest.raises(RuntimeError):
            create_image_media(actor=actor, owner_type="listing", owner_id=owner_listing.listing_id, image=upload())

    assert storage.objects == {}
    assert len(storage.deleted_keys) == 2


def test_upload_and_access_audit_are_safe():
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    media = create_image_media(actor=actor, owner_type="listing", owner_id=listing(actor).listing_id, image=upload(), request=request_for(actor))
    get_media_read_url(actor=actor, media=media, variant=MediaVariant.Kind.DISPLAY, request=request_for(actor))

    upload_log = AuditLog.objects.get(action=MEDIA_UPLOADED)
    access_log = AuditLog.objects.get(action=MEDIA_ACCESSED)
    combined = f"{upload_log.after} {access_log.after}".lower()

    assert upload_log.actor == actor
    assert access_log.actor == actor
    assert media.file_key not in combined
    assert media.file_hash not in combined
    assert "signed-media" not in combined
    assert "gps" not in combined
    assert "exif" not in combined


def test_api_upload_and_access_responses_are_private():
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    owner_listing = listing(actor)
    client = APIClient()
    client.force_authenticate(actor)

    response = client.post(
        "/api/v1/media/images/",
        {
            "owner_type": "listing",
            "owner_id": owner_listing.listing_id,
            "image": upload(),
            "file_key": "client-controlled",
            "file_hash": "client-controlled",
        },
        format="multipart",
    )

    assert response.status_code == 400

    response = client.post(
        "/api/v1/media/images/",
        {"owner_type": "listing", "owner_id": owner_listing.listing_id, "image": upload()},
        format="multipart",
    )
    assert response.status_code == 201
    payload = response.json()
    assert "file_key" not in payload
    assert "file_hash" not in payload
    assert "bucket" not in payload

    access = client.get(f"/api/v1/media/{payload['media_id']}/access/")
    assert access.status_code == 200
    access_payload = access.json()
    assert "file_key" not in access_payload
    assert access_payload["url"].startswith("signed-media:")


def test_upload_boundaries_leave_existing_domains_unchanged():
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    owner_listing = listing(actor)
    create_image_media(actor=actor, owner_type="listing", owner_id=owner_listing.listing_id, image=upload())

    eligibility = check_listing_activation_eligibility(listing=owner_listing)
    requirements = {requirement.code: requirement.status for requirement in eligibility.requirements}
    assert requirements["listing_required_media"] == "UNSATISFIED"
    assert not hasattr(PropertyRecord, "possible_duplicates")
    assert "national_id_photo_ref" in {field.name for field in ListerIdentity._meta.get_fields()}
    assert "live_selfie_ref" in {field.name for field in ListerIdentity._meta.get_fields()}
