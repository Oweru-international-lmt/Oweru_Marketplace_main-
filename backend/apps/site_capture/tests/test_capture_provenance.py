import io
import struct
from datetime import timedelta
import pytest
from PIL import Image
from django.contrib.gis.geos import Point, Polygon, MultiPolygon
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, connection, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.professionals.tests.test_professionals import storage
from apps.site_capture.evidence import upload_capture_asset, provenance_flags, video_metadata
from apps.site_capture.models import PublicMapLayer
from apps.site_capture.services import submit_site_capture
from .test_full_check_measurements import capture_fixture

pytestmark = pytest.mark.django_db


def image_file():
    data = io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(data, format="PNG")
    return SimpleUploadedFile("site.png", data.getvalue(), content_type="image/png")


def atom(kind, payload):
    return struct.pack(">I4s", len(payload) + 8, kind) + payload


def test_camera_and_gallery_images_record_missing_location_and_source():
    owner, _, capture = capture_fixture()
    for source in ["CAMERA", "UPLOAD"]:
        asset = upload_capture_asset(actor=owner, site_capture=capture, file=image_file(), source=source, device="browser")
        assert asset.source == asset.media.source == source
        assert "MEDIA_LOCATION_MISSING" in asset.flags
        assert not asset.media.file_key.startswith("http")


def test_provenance_audit_failure_rolls_back_private_image_objects():
    from unittest.mock import patch
    from apps.media.storage import get_private_media_storage
    owner, _, capture = capture_fixture()
    before = set(get_private_media_storage().objects)
    with patch("apps.site_capture.evidence.create_audit_log", side_effect=RuntimeError("Audit unavailable")):
        with pytest.raises(RuntimeError):
            upload_capture_asset(actor=owner, site_capture=capture, file=image_file(), source="CAMERA")
    assert set(get_private_media_storage().objects) == before and not capture.assets.exists()


def test_postgis_distance_and_configured_age_flags():
    _, _, capture = capture_fixture()
    flags, distance = provenance_flags(location=Point(39.8, -6.9, srid=4326), captured_at=timezone.now() - timedelta(days=31), capture=capture)
    assert distance > 200
    assert set(flags) == {"MEDIA_LOCATION_DISTANT", "MEDIA_DATE_OLD"}
    flags, _ = provenance_flags(location=capture.observed_point, captured_at=timezone.now(), capture=capture)
    assert flags == []


def test_mp4_file_time_and_location_are_extracted_and_privately_stored():
    owner, _, capture = capture_fixture()
    stamp = int((timezone.now() - timezone.datetime(1904, 1, 1, tzinfo=timezone.get_fixed_timezone(0))).total_seconds())
    data = atom(b"ftyp", b"isom\x00\x00\x00\x00isom") + atom(b"moov", atom(b"mvhd", b"\x00\x00\x00\x00" + struct.pack(">II", stamp, stamp)) + atom(b"udta", atom(b"\xa9xyz", b"-06.7924+039.2083/")))
    location, captured_at = video_metadata(data)
    assert location.x == 39.2083 and location.y == -6.7924
    assert captured_at is not None
    asset = upload_capture_asset(actor=owner, site_capture=capture, file=SimpleUploadedFile("site.mp4", data, content_type="video/mp4"), source="CAMERA")
    assert asset.media.mime_type == "video/mp4"
    assert asset.media.captured_location == location


def test_invalid_video_and_other_actor_are_rejected():
    owner, _, capture = capture_fixture()
    with pytest.raises(ValidationError):
        upload_capture_asset(actor=owner, site_capture=capture, file=SimpleUploadedFile("bad.mp4", b"not a video", content_type="video/mp4"), source="UPLOAD")
    from apps.professionals.tests.test_professionals import account
    with pytest.raises(PermissionDenied):
        upload_capture_asset(actor=account("buyer"), site_capture=capture, file=image_file(), source="CAMERA")


def test_loaded_public_layer_overlap_is_frozen_with_geometry_and_osm_fallback():
    owner, _, capture = capture_fixture()
    boundary = Polygon(((39.2083, -6.7924), (39.2086, -6.7924), (39.2086, -6.7921), (39.2083, -6.7924)), srid=4326)
    capture.observed_boundary = boundary
    capture.save()
    PublicMapLayer.objects.create(name="Road reserve", source_reference="Official public layer fixture", boundary=MultiPolygon(boundary, srid=4326), loaded_by=owner)
    capture = submit_site_capture(actor=owner, site_capture=capture)
    assert any(row["kind"] == "PUBLIC_LAYER" and row["geometry"]["type"] == "MultiPolygon" for row in capture.overlap_findings)
    assert "SATELLITE_CHECK_UNAVAILABLE" in capture.review_flags
    from apps.site_capture.serializers import SiteCapturePrivateSerializer
    assert SiteCapturePrivateSerializer(capture).data["map_context"]["provider"] == "OPENSTREETMAP"


def test_submitted_capture_media_and_variants_resist_direct_updates():
    owner, _, capture = capture_fixture()
    asset = upload_capture_asset(actor=owner, site_capture=capture, file=image_file(), source="CAMERA")
    capture.observed_boundary = Polygon(((39.2083, -6.7924), (39.2086, -6.7924), (39.2086, -6.7921), (39.2083, -6.7924)), srid=4326)
    capture.save()
    submit_site_capture(actor=owner, site_capture=capture)
    with pytest.raises(ValidationError):
        upload_capture_asset(actor=owner, site_capture=capture, file=image_file(), source="CAMERA")
    for sql, value in [("UPDATE media_media SET file_key='changed' WHERE id=%s", asset.media_id), ("DELETE FROM media_mediavariant WHERE media_id=%s", asset.media_id), ("DELETE FROM site_capture_captureasset WHERE id=%s", asset.pk)]:
        with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(sql, [value])
