"""Private capture media and file-derived provenance; no public upload paths."""
import hashlib
import io
import re
import struct
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from PIL import Image
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import Point
from django.db import connection, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.media.models import Media
from apps.media.storage import get_private_media_storage
from apps.verification.configuration import setting
from apps.verification.task_services import private_write_scope
from apps.audit.services import create_audit_log
from .models import CaptureAsset
from .services import _active_persisted_actor, _resolve_locked_capture, _ensure_can_edit_capture


def image_metadata(data):
    location, captured_at = None, None
    with Image.open(io.BytesIO(data)) as image:
        exif = image.getexif()
        gps = exif.get_ifd(34853) if 34853 in exif else {}
        def degrees(parts):
            return float(parts[0]) + float(parts[1]) / 60 + float(parts[2]) / 3600
        try:
            lat, lon = degrees(gps[2]), degrees(gps[4])
            location = Point(-lon if gps.get(3) in {"W", b"W"} else lon, -lat if gps.get(1) in {"S", b"S"} else lat, srid=4326)
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            pass
        raw_time = exif.get_ifd(34665).get(36867) if 34665 in exif else exif.get(306)
        try:
            # EXIF dates without an offset are observations, interpreted in the project's timezone.
            captured_at = timezone.make_aware(datetime.strptime(raw_time, "%Y:%m:%d %H:%M:%S"))
        except (ValueError, TypeError):
            pass
    return location, captured_at


def video_metadata(data):
    """Read bounded ISO-BMFF MP4 atoms: movie time and QuickTime ISO6709 tags."""
    if len(data) < 12 or data[4:8] != b"ftyp":
        raise ValidationError("A valid MP4 video is required.")
    captured_at, location = None, None
    def atoms(start, end, depth=0):
        nonlocal captured_at, location
        if depth > 8:
            raise ValidationError("Video metadata nesting is invalid.")
        offset = start
        while offset + 8 <= end:
            size, kind = struct.unpack_from(">I4s", data, offset)
            header = 8
            if size == 1:
                if offset + 16 > end:
                    raise ValidationError("Truncated video atom.")
                size, header = struct.unpack_from(">Q", data, offset + 8)[0], 16
            if size == 0:
                size = end - offset
            if size < header or offset + size > end:
                raise ValidationError("Invalid video atom length.")
            payload = offset + header
            if kind == b"mvhd" and payload + 12 <= offset + size:
                version = data[payload]
                width = 8 if version == 1 else 4
                if version not in {0, 1} or payload + 4 + width > offset + size:
                    raise ValidationError("Invalid video timestamp.")
                seconds = int.from_bytes(data[payload + 4:payload + 4 + width], "big")
                if seconds:
                    try:
                        captured_at = datetime(1904, 1, 1, tzinfo=dt_timezone.utc) + timedelta(seconds=seconds)
                    except OverflowError:
                        pass
            if kind in {b"moov", b"udta"}:
                atoms(payload, offset + size, depth + 1)
            if kind in {b"meta", b"\xa9xyz"}:
                metadata = data[payload:offset + size]
                if kind == b"\xa9xyz" or b"location.ISO6709" in metadata:
                    match = re.search(rb"([+-]\d{2}(?:\.\d+)?)([+-]\d{3}(?:\.\d+)?)(?:[+-]\d+(?:\.\d+)?)?/", metadata)
                    if match:
                        lat, lon = float(match[1]), float(match[2])
                        if -90 <= lat <= 90 and -180 <= lon <= 180:
                            location = Point(lon, lat, srid=4326)
            offset += size
    atoms(0, len(data))
    return location, captured_at


def provenance_flags(*, location, captured_at, capture):
    flags, distance = [], None
    if location is None:
        flags.append("MEDIA_LOCATION_MISSING")
    else:
        with connection.cursor() as cursor:
            cursor.execute("SELECT ST_Distance(ST_GeomFromEWKT(%s)::geography, ST_GeomFromEWKT(%s)::geography)", [location.ewkt, capture.observed_point.ewkt])
            distance = Decimal(str(cursor.fetchone()[0])).quantize(Decimal("0.01"))
        if distance > Decimal(str(setting("photo_distance_m"))):
            flags.append("MEDIA_LOCATION_DISTANT")
    if captured_at and captured_at < timezone.now() - timedelta(days=float(setting("photo_age_days"))):
        flags.append("MEDIA_DATE_OLD")
    return flags, distance


def upload_capture_asset(*, actor, site_capture, file, source, device="", request=None):
    if source not in {"CAMERA", "UPLOAD"} or len(device) > 255:
        raise ValidationError("Camera/gallery source and a valid device are required.")
    # A bounded upload is read once; image processing retains its own existing validation.
    if not file.size or file.size > 50 * 1024 * 1024:
        raise ValidationError("Capture media must be at most 50 MB.")
    data = file.read(50 * 1024 * 1024 + 1)
    file.seek(0)
    with private_write_scope(), transaction.atomic():
        actor = _active_persisted_actor(actor)
        capture = _resolve_locked_capture(site_capture)
        _ensure_can_edit_capture(actor, capture)
        if capture.status != "DRAFT":
            raise ValidationError("Submitted capture media is locked.")
        if file.content_type == "video/mp4":
            location, captured_at = video_metadata(data)
            key = f"site-capture/{capture.pk}/{uuid.uuid4().hex}.mp4"
            from apps.payments.documents import pending_objects
            storage = get_private_media_storage()
            pending_objects.get().append((storage, key))
            storage.save_private_object(key=key, content=io.BytesIO(data), content_type="video/mp4")
            media = Media.objects.create(content_type=ContentType.objects.get_for_model(capture), object_id=capture.pk, uploaded_by=actor, file_key=key, source=source, captured_at=captured_at, captured_location=location, device=device, file_hash=hashlib.sha256(data).hexdigest(), mime_type="video/mp4", size_bytes=len(data))
        elif file.content_type in {"image/jpeg", "image/png"}:
            from apps.media.services import _create_image_media_for_owner
            try:
                location, captured_at = image_metadata(data)
            except (OSError, ValueError) as exc:
                raise ValidationError("Invalid capture image.") from exc
            media = _create_image_media_for_owner(actor=actor, owner=capture, image=file, source=source, captured_at=captured_at, captured_location=location, device=device, request=request)
        else:
            raise ValidationError("Capture evidence supports JPEG, PNG and MP4.")
        flags, distance = provenance_flags(location=location, captured_at=captured_at, capture=capture)
        asset = CaptureAsset.objects.create(capture=capture, media=media, source=source, flags=flags, distance_m=distance)
        create_audit_log(actor=actor, action="site_capture.provenance_recorded", entity_type="CaptureAsset", entity_id=asset.pk, before={}, after={"source": source, "flags": flags}, request=request)
        return asset
