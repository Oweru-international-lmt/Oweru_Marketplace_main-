from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.audit.models import AuditLog
from apps.media.audit_events import MEDIA_ACCESSED, MEDIA_DELETED, MEDIA_UPLOADED
from apps.media.models import Media, MediaVariant
from apps.media.serializers import MediaSafeSerializer
from apps.media.services import create_image_media, get_media, get_media_read_url
from apps.media.storage import get_private_media_storage, reset_in_memory_storage
from apps.properties.models import PropertyRecord
from apps.roles.catalog import ROLE_MANAGEMENT, ROLE_OWNER
from apps.roles.models import Role, UserRole
from apps.roles.services import bootstrap_canonical_roles
from apps.localities.models import District, Locality, Region, Ward
from apps.site_capture.models import SiteCapture
from apps.site_capture.services import (
    create_site_capture,
    remove_site_capture_media,
    submit_site_capture,
    upload_site_capture_image,
)
from apps.verification.services import get_effective_verification_level


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


def image_bytes(fmt="JPEG", size=(32, 24)):
    image = Image.new("RGB", size, color=(90, 120, 150))
    output = BytesIO()
    image.save(output, format=fmt)
    return output.getvalue()


def upload(fmt="JPEG", content_type="image/jpeg", name="capture.jpg"):
    return SimpleUploadedFile(name, image_bytes(fmt), content_type=content_type)


def create_user(email=None):
    email = email or f"capture-media-{uuid.uuid4().hex[:10]}@example.test"
    return get_user_model().objects.create_user(
        email=email,
        phone=f"+2557{abs(hash(email)) % 100000000:08d}",
        full_name="Site Capture Media User",
        password="StrongPass123!",
    )


def grant_role(user, role_code):
    bootstrap_canonical_roles()
    return UserRole.objects.create(user=user, role=Role.objects.get(code=role_code))


def property_record(owner, prefix=None):
    prefix = prefix or f"CaptureMedia{uuid.uuid4().hex[:8]}"
    region = Region.objects.create(name=f"{prefix} Region")
    district = District.objects.create(region=region, name=f"{prefix} District")
    ward = Ward.objects.create(district=district, name=f"{prefix} Ward")
    locality = Locality.objects.create(ward=ward, name=f"{prefix} Street", kind=Locality.Kind.STREET, approved=True)
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


def capture(owner, property_record):
    return create_site_capture(
        property_record=property_record,
        actor=owner,
        observed_point=Point(39.21, -6.79, srid=4326),
    )


def owner_capture(prefix="CaptureMedia"):
    owner = create_user(f"{prefix.lower()}@example.test")
    grant_role(owner, ROLE_OWNER)
    property_record_instance = property_record(owner, prefix)
    return owner, property_record_instance, capture(owner, property_record_instance)


@pytest.mark.parametrize(
    ("fmt", "content_type"),
    [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")],
)
def test_draft_capture_upload_reuses_canonical_media_pipeline(fmt, content_type):
    owner, property_record_instance, site_capture = owner_capture(f"Upload{fmt}")

    media = upload_site_capture_image(
        site_capture=site_capture,
        actor=owner,
        image=upload(fmt, content_type),
        captured_at=timezone.now() - timedelta(minutes=1),
        captured_location={"type": "Point", "coordinates": [39.22, -6.78]},
        device="Private field device",
    )

    assert media.owner == site_capture
    assert media.content_type == ContentType.objects.get_for_model(SiteCapture)
    assert media.object_id == site_capture.pk
    assert media.source == Media.Source.SITE_CAPTURE
    assert media.captured_location.srid == 4326
    assert media.file_hash and len(media.file_hash) == 64
    assert set(media.variants.values_list("kind", flat=True)) == {MediaVariant.Kind.ORIGINAL, MediaVariant.Kind.DISPLAY}
    assert get_private_media_storage().exists(key=media.file_key)
    assert property_record_instance.site_captures.count() == 1


def test_capture_media_metadata_is_private_and_invalid_location_rejected():
    owner, _, site_capture = owner_capture("Metadata")
    media = upload_site_capture_image(
        site_capture=site_capture,
        actor=owner,
        image=upload(),
        captured_location=Point(39.22, -6.78, srid=4326),
        device="private-device",
    )

    payload = MediaSafeSerializer(media).data
    assert {"file_key", "file_hash", "captured_location", "device"}.isdisjoint(payload)
    with pytest.raises(ValidationError):
        upload_site_capture_image(
            site_capture=site_capture,
            actor=owner,
            image=upload(),
            captured_location={"type": "Point", "coordinates": [181, 0]},
        )
    assert Media.objects.count() == 1


def test_site_capture_upload_enforces_authority_persisted_roles_and_draft_status():
    owner, _, site_capture = owner_capture("Authority")
    unrelated = create_user("capture-media-unrelated@example.test")
    unrelated.role = ROLE_OWNER
    unrelated.roles = [ROLE_OWNER]

    with pytest.raises(PermissionDenied):
        upload_site_capture_image(site_capture=site_capture, actor=unrelated, image=upload())

    submit_site_capture(site_capture=site_capture, actor=owner)
    with pytest.raises(ValidationError):
        upload_site_capture_image(site_capture=site_capture, actor=owner, image=upload())
    assert Media.objects.count() == 0


def test_generic_upload_cannot_select_site_capture_source_or_owner():
    owner, property_record_instance, site_capture = owner_capture("SourceControl")

    with pytest.raises(ValidationError):
        create_image_media(
            actor=owner,
            owner_type="property_record",
            owner_id=property_record_instance.property_id,
            image=upload(),
            source=Media.Source.SITE_CAPTURE,
        )
    with pytest.raises(ValidationError):
        create_image_media(
            actor=owner,
            owner_type="site_capture",
            owner_id=str(site_capture.pk),
            image=upload(),
        )
    assert Media.objects.count() == 0


def test_management_can_upload_via_canonical_property_authority():
    owner, _, site_capture = owner_capture("Management")
    management = create_user("capture-media-management@example.test")
    grant_role(management, ROLE_MANAGEMENT)

    media = upload_site_capture_image(site_capture=site_capture, actor=management, image=upload())

    assert media.uploaded_by == management


def test_authorized_access_uses_private_signed_url_and_unrelated_or_guessed_access_fails():
    owner, _, site_capture = owner_capture("Access")
    media = upload_site_capture_image(site_capture=site_capture, actor=owner, image=upload())
    response = get_media_read_url(actor=owner, media=media, variant=MediaVariant.Kind.DISPLAY)

    assert response == {
        "media_id": media.media_id,
        "variant": MediaVariant.Kind.DISPLAY,
        "url": response["url"],
        "expires_in": 123,
    }
    assert media.file_key not in response["url"]
    assert response["url"].startswith("signed-media:")
    unrelated = create_user("capture-media-access-unrelated@example.test")
    with pytest.raises(PermissionDenied):
        get_media(actor=unrelated, media_id=media.media_id)
    with pytest.raises(NotFound):
        get_media(actor=unrelated, media_id="MED-DOESNOTEXIST")


@pytest.mark.django_db(transaction=True)
def test_draft_removal_deletes_canonical_media_and_private_variants_after_commit():
    owner, _, site_capture = owner_capture("Removal")
    media = upload_site_capture_image(site_capture=site_capture, actor=owner, image=upload())
    keys = list(media.variants.values_list("file_key", flat=True))

    remove_site_capture_media(site_capture=site_capture, media=media, actor=owner)

    assert not Media.objects.filter(pk=media.pk).exists()
    assert all(not get_private_media_storage().exists(key=key) for key in keys)
    audit = AuditLog.objects.get(action=MEDIA_DELETED)
    assert audit.after["capture_id"] == site_capture.capture_id
    assert audit.after["property_id"] == str(site_capture.property_id)


def test_capture_media_removal_enforces_exact_owner_and_submitted_freeze():
    owner, _, first_capture = owner_capture("FirstRemoval")
    second_capture = capture(owner, first_capture.property)
    media = upload_site_capture_image(site_capture=first_capture, actor=owner, image=upload())
    unrelated = create_user("capture-media-removal-unrelated@example.test")

    with pytest.raises(PermissionDenied):
        remove_site_capture_media(site_capture=first_capture, media=media, actor=unrelated)
    with pytest.raises(NotFound):
        remove_site_capture_media(site_capture=second_capture, media=media, actor=owner)

    submit_site_capture(site_capture=first_capture, actor=owner)
    with pytest.raises(ValidationError):
        remove_site_capture_media(site_capture=first_capture, media=media, actor=owner)


def test_upload_failure_cleans_private_objects_and_creates_no_media_or_audit():
    owner, _, site_capture = owner_capture("StorageFailure")

    class FailingStorage:
        def __init__(self):
            self.saved = []
            self.deleted = []

        def save_private_object(self, *, key, content, content_type=None):
            self.saved.append(key)
            if len(self.saved) == 2:
                raise RuntimeError("display save failed")
            return key

        def delete_private_object(self, *, key):
            self.deleted.append(key)

    storage = FailingStorage()
    with patch("apps.media.services.get_private_media_storage", return_value=storage):
        with pytest.raises(RuntimeError, match="display save failed"):
            upload_site_capture_image(site_capture=site_capture, actor=owner, image=upload())

    assert storage.deleted == storage.saved[:1]
    assert Media.objects.count() == 0
    assert not AuditLog.objects.filter(action=MEDIA_UPLOADED).exists()


def test_media_audit_has_safe_capture_context_without_private_metadata():
    owner, property_record_instance, site_capture = owner_capture("Audit")
    level_before = get_effective_verification_level(user=owner, property_record=property_record_instance)
    media = upload_site_capture_image(
        site_capture=site_capture,
        actor=owner,
        image=upload(),
        captured_location={"type": "Point", "coordinates": [39.25, -6.75]},
        device="sensitive-device",
    )
    get_media_read_url(actor=owner, media=media)

    events = AuditLog.objects.filter(action__in=[MEDIA_UPLOADED, MEDIA_ACCESSED])
    serialized = " ".join(str(event.before) + str(event.after) for event in events)
    for forbidden in (media.file_key, media.file_hash, "39.25", "-6.75", "sensitive-device", "signed-media"):
        assert forbidden not in serialized
    assert get_effective_verification_level(user=owner, property_record=property_record_instance) == level_before
