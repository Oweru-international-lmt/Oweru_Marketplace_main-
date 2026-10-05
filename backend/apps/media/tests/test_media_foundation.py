import uuid
from unittest.mock import patch

import pytest
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import override_settings

from apps.accounts.models import User
from apps.media.models import Media
from apps.media.storage import get_media_storage_config, get_private_media_storage


pytestmark = pytest.mark.django_db


def user(email="media-owner@example.test"):
    return User.objects.create_user(
        email=email,
        phone=f"+2557{abs(hash(email)) % 100000000:08d}",
        full_name="Media Owner",
        password="StrongerPass123!",
    )


def media(owner, **overrides):
    content_type = ContentType.objects.get_for_model(owner)
    attrs = {
        "content_type": content_type,
        "object_id": owner.pk,
        "uploaded_by": owner if isinstance(owner, User) else None,
        "file_key": "media/private/object.jpg",
        "source": Media.Source.UPLOAD,
        "mime_type": "image/jpeg",
        "size_bytes": 1200,
        "file_hash": "sha256:" + "a" * 64,
    }
    attrs.update(overrides)
    return Media(**attrs)


def test_media_app_is_registered_canonically():
    app_config = apps.get_app_config("media")

    assert app_config.name == "apps.media"
    assert app_config.label == "media"


def test_media_creation_with_owner_entity_relationship():
    owner = user()
    item = media(owner)
    item.full_clean()
    item.save()

    assert item.owner == owner
    assert item.media_id.startswith("MED-")
    assert len(item.media_id) == 20
    assert item.uploaded_by == owner


def test_media_id_is_unique_and_retries_on_collision():
    owner = user("collision-owner@example.test")
    first = media(owner, media_id="MED-AAAAAAAAAAAAAAAA")
    first.full_clean()
    first.save()

    second = media(owner, media_id=first.media_id, file_key="media/private/second.jpg")
    with patch("apps.media.models.generate_media_id", return_value="MED-BBBBBBBBBBBBBBBB"):
        second.save()

    assert second.media_id == "MED-BBBBBBBBBBBBBBBB"
    assert Media.objects.filter(media_id__in=[first.media_id, second.media_id]).count() == 2


@pytest.mark.parametrize(
    "file_key",
    [
        "",
        "/tmp/private.jpg",
        "file:///tmp/private.jpg",
        "https://example.test/private.jpg",
        "http://example.test/private.jpg",
        "s3://bucket/private.jpg",
        "../private.jpg",
        "media/../private.jpg",
        r"media\private.jpg",
    ],
)
def test_invalid_file_key_forms_are_rejected(file_key):
    item = media(user(f"invalid-key-{uuid.uuid4()}@example.test"), file_key=file_key)

    with pytest.raises(ValidationError) as exc:
        item.full_clean()

    assert "file_key" in exc.value.message_dict


def test_file_key_is_normalized_without_exposing_filesystem_paths():
    item = media(user("normalize-key@example.test"), file_key=" media//private/object.jpg ")
    item.full_clean()

    assert item.file_key == "media/private/object.jpg"


def test_mime_type_size_hash_and_nullable_capture_metadata():
    item = media(
        user("metadata@example.test"),
        mime_type=" Image/JPEG ",
        size_bytes=42,
        file_hash="sha256:" + "b" * 64,
        captured_at=None,
        captured_location=None,
        device="",
    )
    item.full_clean()

    assert item.mime_type == "image/jpeg"
    assert item.size_bytes == 42
    assert item.file_hash.startswith("sha256:")
    assert item.captured_at is None
    assert item.captured_location is None


def test_capture_location_accepts_gis_point_when_available():
    item = media(user("capture-point@example.test"), captured_location=Point(39.2083, -6.7924, srid=4326))
    item.full_clean()
    item.save()

    assert item.captured_location.srid == 4326


@pytest.mark.parametrize("size_bytes", [0, -1])
def test_size_must_be_positive(size_bytes):
    item = media(user(f"size-{size_bytes}@example.test"), size_bytes=size_bytes)

    with pytest.raises(ValidationError) as exc:
        item.full_clean()

    assert "size_bytes" in exc.value.message_dict


def test_missing_owner_entity_is_rejected():
    content_type = ContentType.objects.get_for_model(User)
    item = Media(
        content_type=content_type,
        object_id=uuid.uuid4(),
        file_key="media/private/missing-owner.jpg",
        mime_type="image/jpeg",
        size_bytes=10,
    )

    with pytest.raises(ValidationError) as exc:
        item.full_clean()

    assert "object_id" in exc.value.message_dict


def test_database_enforces_media_id_uniqueness():
    owner = user("unique-db@example.test")
    media(owner, media_id="MED-CCCCCCCCCCCCCCCC").save()

    duplicate = media(owner, media_id="MED-CCCCCCCCCCCCCCCC", file_key="media/private/duplicate.jpg")
    with patch("apps.media.models.generate_media_id", return_value="MED-CCCCCCCCCCCCCCCC"):
        with pytest.raises(IntegrityError):
            duplicate.save()


@override_settings(
    MEDIA_STORAGE_BACKEND="unconfigured",
    MEDIA_STORAGE_BUCKET="",
    MEDIA_STORAGE_ENDPOINT="",
    MEDIA_SIGNED_URL_TTL_SECONDS=300,
)
def test_private_storage_defaults_to_unconfigured_and_no_public_url_behavior():
    config = get_media_storage_config()
    storage = get_private_media_storage()

    assert config.backend == "unconfigured"
    assert config.signed_url_ttl_seconds == 300
    with pytest.raises(RuntimeError):
        storage.generate_signed_read_url(key="media/private/object.jpg")


def test_no_listing_property_or_lister_identity_schema_integration_yet():
    listing_fields = {field.name for field in apps.get_model("listings", "Listing")._meta.get_fields()}
    property_fields = {field.name for field in apps.get_model("properties", "PropertyRecord")._meta.get_fields()}
    identity_fields = {field.name for field in apps.get_model("lister_identity", "ListerIdentity")._meta.get_fields()}

    assert "media" not in listing_fields
    assert "media" not in property_fields
    assert "media" not in identity_fields
    assert "national_id_photo_ref" in identity_fields
    assert "live_selfie_ref" in identity_fields
