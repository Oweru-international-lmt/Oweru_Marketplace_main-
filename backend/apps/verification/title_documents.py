"""The lister's title document for the location check: a photo or a scanned PDF.

The file is checked by its content, not only its name: a PDF must start with
the PDF header and end with the end-of-file marker, and an image must open as
the image type it claims. It is stored as the property record's private media,
so only the verifier on the check can open it (review_desk.DocumentEvidenceView).
"""
import hashlib
import uuid
from io import BytesIO
from pathlib import PurePath

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from drf_spectacular.utils import extend_schema
from PIL import Image
from rest_framework import generics, serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.audit.services import create_audit_log
from apps.media.audit_events import MEDIA_UPLOADED
from apps.media.models import Media
from apps.media.storage import get_private_media_storage
from apps.properties.policies import can_update_property_record, get_active_persisted_actor
from apps.properties.services import get_property_record

from .serializers import StrictInputSerializer

IMAGE_TYPES = {"JPEG": ("image/jpeg", {".jpg", ".jpeg"}), "PNG": ("image/png", {".png"}), "WEBP": ("image/webp", {".webp"})}
INVALID = "Use a PDF, JPEG, PNG or WEBP file whose name matches its content."


def validate_title_document(upload):
    if upload.size <= 0 or upload.size > settings.MEDIA_MAX_UPLOAD_BYTES:
        raise ValidationError({"document": "The file must be between 1 byte and 5 MB."})
    upload.seek(0)
    content = upload.read(settings.MEDIA_MAX_UPLOAD_BYTES + 1)
    upload.seek(0)
    if not content or len(content) > settings.MEDIA_MAX_UPLOAD_BYTES:
        raise ValidationError({"document": "The file must be between 1 byte and 5 MB."})
    extension = PurePath(upload.name or "").suffix.lower()
    if content.startswith(b"%PDF-"):
        if extension != ".pdf" or b"%%EOF" not in content[-2048:]:
            raise ValidationError({"document": INVALID})
        return content, "application/pdf"
    try:
        with Image.open(BytesIO(content)) as image:
            kind = image.format
            image.verify()
    except Exception as exc:  # noqa: BLE001 - anything unreadable is refused
        raise ValidationError({"document": INVALID}) from exc
    mime, extensions = IMAGE_TYPES.get(kind, (None, set()))
    if mime is None or extension not in extensions:
        raise ValidationError({"document": INVALID})
    return content, mime


class TitleDocumentUploadSerializer(StrictInputSerializer):
    document = serializers.FileField()


class TitleDocumentView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = TitleDocumentUploadSerializer

    @extend_schema(request=TitleDocumentUploadSerializer, responses={201: {"type": "object"}})
    def post(self, request, property_id, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        property_record = get_property_record(actor=request.user, property_id=property_id)
        actor = get_active_persisted_actor(request.user)
        if actor is None or not can_update_property_record(actor, property_record):
            raise PermissionDenied("You cannot add documents to this property.")
        content, mime = validate_title_document(serializer.validated_data["document"])
        media = save_title_document(actor=actor, property_record=property_record, content=content, mime=mime, request=request)
        return Response(
            {"media_id": media.media_id, "mime_type": media.mime_type, "size_bytes": media.size_bytes, "created_at": media.created_at},
            status=status.HTTP_201_CREATED,
        )


@transaction.atomic
def save_title_document(*, actor, property_record, content, mime, request=None):
    storage = get_private_media_storage()
    key = f"title-documents/{property_record.pk}/{uuid.uuid4().hex}"
    storage.save_private_object(key=key, content=BytesIO(content), content_type=mime)
    try:
        media = Media.objects.create(
            content_type=ContentType.objects.get_for_model(property_record),
            object_id=property_record.pk,
            uploaded_by=actor,
            file_key=key,
            mime_type=mime,
            file_hash=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
            device=(request.META.get("HTTP_USER_AGENT", "")[:255] if request else ""),
        )
    except Exception:
        storage.delete_private_object(key=key)
        raise
    create_audit_log(
        actor=actor,
        action=MEDIA_UPLOADED,
        entity_type="Media",
        entity_id=media.pk,
        before={},
        after={"media_id": media.media_id, "owner_type": "property_record", "property_id": property_record.property_id, "mime_type": mime, "purpose": "title_document"},
        request=request,
    )
    return media
