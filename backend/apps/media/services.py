from io import BytesIO
from secrets import token_hex

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.audit.services import create_audit_log
from apps.listings.models import Listing
from apps.listings.policies import can_update_listing, can_view_listing, get_active_persisted_actor as active_listing_actor
from apps.properties.models import PropertyRecord
from apps.properties.policies import can_update_property_record, can_view_property_record

from .audit_events import MEDIA_ACCESSED, MEDIA_UPLOADED
from .images import validate_and_process_image_upload
from .models import MEDIA_ID_MAX_COLLISION_RETRIES, Media, MediaVariant, generate_media_id
from .storage import get_private_media_storage


SUPPORTED_OWNER_TYPES = {
    "listing": Listing,
    "property_record": PropertyRecord,
}
OWNER_LOOKUP_FIELDS = {
    "listing": "listing_id",
    "property_record": "property_id",
}


def _active_actor(actor):
    persisted = active_listing_actor(actor)
    if persisted is None:
        raise PermissionDenied("An active persisted account is required.")
    return persisted


def _resolve_owner(*, owner_type, owner_id):
    owner_type = (owner_type or "").strip().lower()
    model = SUPPORTED_OWNER_TYPES.get(owner_type)
    if model is None:
        raise ValidationError({"owner_type": "Unsupported media owner type."})
    lookup_field = OWNER_LOOKUP_FIELDS[owner_type]
    try:
        return owner_type, model.objects.get(**{lookup_field: owner_id})
    except model.DoesNotExist as exc:
        raise NotFound("Media owner was not found.") from exc


def _ensure_can_upload(actor, owner):
    if isinstance(owner, Listing) and can_update_listing(actor, owner):
        return
    if isinstance(owner, PropertyRecord) and can_update_property_record(actor, owner):
        return
    raise PermissionDenied("You cannot upload media for this owner.")


def _ensure_can_access(actor, media):
    owner = media.owner
    if isinstance(owner, Listing) and can_view_listing(actor, owner):
        return owner
    if isinstance(owner, PropertyRecord) and can_view_property_record(actor, owner):
        return owner
    raise PermissionDenied("You cannot access this media.")


def _generate_unique_media_id():
    for _ in range(MEDIA_ID_MAX_COLLISION_RETRIES):
        candidate = generate_media_id()
        if not Media.objects.filter(media_id=candidate).exists():
            return candidate
    raise ValidationError({"media_id": "Could not generate a unique media identifier."})


def _object_key(*, kind, media_id, mime_type):
    extension = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }[mime_type]
    return f"{kind.lower()}s/{media_id}/{token_hex(16)}.{extension}"


def _safe_owner_label(owner):
    if isinstance(owner, Listing):
        return "Listing"
    if isinstance(owner, PropertyRecord):
        return "PropertyRecord"
    return owner.__class__.__name__


def _safe_owner_public_id(owner):
    if isinstance(owner, Listing):
        return owner.listing_id
    if isinstance(owner, PropertyRecord):
        return owner.property_id
    return ""


def _audit_upload(*, actor, media, owner, request=None):
    create_audit_log(
        actor=actor,
        action=MEDIA_UPLOADED,
        entity_type="Media",
        entity_id=media.pk,
        before={},
        after={
            "media_id": media.media_id,
            "owner_type": _safe_owner_label(owner),
            "owner_id": _safe_owner_public_id(owner),
            "source": media.source,
            "mime_type": media.mime_type,
            "variants": sorted(media.variants.values_list("kind", flat=True)),
        },
        request=request,
    )


def _audit_access(*, actor, media, variant, request=None):
    create_audit_log(
        actor=actor,
        action=MEDIA_ACCESSED,
        entity_type="Media",
        entity_id=media.pk,
        before={},
        after={
            "media_id": media.media_id,
            "variant": variant.kind,
        },
        request=request,
    )


def _cleanup(storage, keys):
    for key in keys:
        try:
            storage.delete_private_object(key=key)
        except Exception:
            pass


@transaction.atomic
def create_image_media(*, actor, owner_type, owner_id, image, source=Media.Source.UPLOAD, request=None):
    actor = _active_actor(actor)
    owner_type, owner = _resolve_owner(owner_type=owner_type, owner_id=owner_id)
    _ensure_can_upload(actor, owner)
    if source not in {choice.value for choice in Media.Source}:
        raise ValidationError({"source": "Unsupported media source."})
    if source != Media.Source.UPLOAD:
        raise ValidationError({"source": "Only standard upload source is supported for this workflow."})

    processed = validate_and_process_image_upload(image)
    media_id = _generate_unique_media_id()
    original_key = _object_key(kind=MediaVariant.Kind.ORIGINAL, media_id=media_id, mime_type=processed.mime_type)
    display_key = _object_key(kind=MediaVariant.Kind.DISPLAY, media_id=media_id, mime_type=processed.mime_type)
    storage = get_private_media_storage()
    stored_keys = []

    try:
        storage.save_private_object(
            key=original_key,
            content=BytesIO(processed.original_bytes),
            content_type=processed.mime_type,
        )
        stored_keys.append(original_key)
        storage.save_private_object(
            key=display_key,
            content=BytesIO(processed.display_bytes),
            content_type=processed.mime_type,
        )
        stored_keys.append(display_key)

        content_type = ContentType.objects.get_for_model(owner)
        media = Media(
            media_id=media_id,
            content_type=content_type,
            object_id=owner.pk,
            uploaded_by=actor,
            file_key=original_key,
            source=source,
            file_hash=processed.sha256,
            mime_type=processed.mime_type,
            size_bytes=len(processed.original_bytes),
        )
        try:
            media.full_clean()
            media.save()
            MediaVariant.objects.create(
                media=media,
                kind=MediaVariant.Kind.ORIGINAL,
                file_key=original_key,
                mime_type=processed.mime_type,
                size_bytes=len(processed.original_bytes),
                width=processed.original_width,
                height=processed.original_height,
            )
            MediaVariant.objects.create(
                media=media,
                kind=MediaVariant.Kind.DISPLAY,
                file_key=display_key,
                mime_type=processed.mime_type,
                size_bytes=len(processed.display_bytes),
                width=processed.display_width,
                height=processed.display_height,
            )
            _audit_upload(actor=actor, media=media, owner=owner, request=request)
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc
    except Exception:
        _cleanup(storage, stored_keys)
        raise

    return media


def get_media(*, actor, media_id):
    actor = _active_actor(actor)
    try:
        media = Media.objects.select_related("content_type", "uploaded_by").prefetch_related("variants").get(media_id=media_id)
    except Media.DoesNotExist as exc:
        raise NotFound("Media was not found.") from exc
    _ensure_can_access(actor, media)
    return media


def get_media_read_url(*, actor, media, variant=MediaVariant.Kind.DISPLAY, request=None):
    actor = _active_actor(actor)
    if isinstance(media, str):
        media = get_media(actor=actor, media_id=media)
    else:
        _ensure_can_access(actor, media)

    if variant not in {choice.value for choice in MediaVariant.Kind}:
        raise ValidationError({"variant": "Unsupported media variant."})
    try:
        selected = media.variants.get(kind=variant)
    except MediaVariant.DoesNotExist as exc:
        raise NotFound("Media variant was not found.") from exc

    url = get_private_media_storage().generate_signed_read_url(
        key=selected.file_key,
        expires_in=settings.MEDIA_SIGNED_URL_TTL_SECONDS,
    )
    _audit_access(actor=actor, media=media, variant=selected, request=request)
    return {
        "media_id": media.media_id,
        "variant": selected.kind,
        "url": url,
        "expires_in": settings.MEDIA_SIGNED_URL_TTL_SECONDS,
    }
