import hashlib
import uuid
from contextvars import ContextVar
from io import BytesIO
from pathlib import PurePath
from PIL import Image
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from rest_framework.exceptions import ValidationError
from apps.media.models import Media
from apps.media.storage import get_private_media_storage

pending_objects = ContextVar("financial_private_objects", default=None)


def validate_document(upload):
    if upload.size <= 0 or upload.size > settings.MEDIA_MAX_UPLOAD_BYTES:
        raise ValidationError("Document size is invalid.")
    upload.seek(0)
    content = upload.read(settings.MEDIA_MAX_UPLOAD_BYTES + 1)
    upload.seek(0)
    if not content or len(content) > settings.MEDIA_MAX_UPLOAD_BYTES:
        raise ValidationError("Document size is invalid.")
    ext = PurePath(upload.name).suffix.lower()
    mime = getattr(upload, "content_type", "")
    if ext == ".pdf" and mime == "application/pdf" and content.startswith(b"%PDF-") and b"%%EOF" in content[-2048:]:
        actual = "application/pdf"
    else:
        try:
            with Image.open(BytesIO(content)) as image:
                actual = {"JPEG": "image/jpeg", "PNG": "image/png"}.get(image.format)
                image.verify()
        except Exception:
            actual = None
        extensions = {"image/jpeg": {".jpg", ".jpeg"}, "image/png": {".png"}}
        if actual != mime or ext not in extensions.get(actual, set()):
            raise ValidationError("Use a valid PDF, JPEG or PNG with matching extension and MIME type.")
    return content, actual, hashlib.sha256(content).hexdigest()


def save_document(*, actor, owner, upload):
    content, mime, digest = validate_document(upload)
    storage = get_private_media_storage()
    key = f"financial/{owner.pk}/{uuid.uuid4().hex}"
    storage.save_private_object(key=key, content=BytesIO(content), content_type=mime)
    pending = pending_objects.get()
    if pending is not None:
        pending.append((storage, key))
    try:
        media = Media.objects.create(content_type=ContentType.objects.get_for_model(owner), object_id=owner.pk, uploaded_by=actor, file_key=key, mime_type=mime, file_hash=digest, size_bytes=len(content))
    except Exception:
        storage.delete_private_object(key=key)
        raise
    return media
