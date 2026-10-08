from collections.abc import Mapping
from io import BytesIO
from secrets import token_hex

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.audit.services import create_audit_log
from apps.listings.models import Listing
from apps.listings.policies import can_update_listing, can_view_listing, get_active_persisted_actor as active_listing_actor
from apps.properties.models import PropertyRecord
from apps.properties.policies import can_update_property_record, can_view_property_record
from apps.properties.serializers import GeoJSONPointField
from apps.site_capture.models import SiteCapture

from .audit_events import MEDIA_ACCESSED, MEDIA_DELETED, MEDIA_UPLOADED
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
    if isinstance(owner, SiteCapture):
        from apps.site_capture.services import _ensure_can_read_capture
        _ensure_can_read_capture(actor, owner)
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
    if isinstance(owner, SiteCapture):
        return "SiteCapture"
    return owner.__class__.__name__


def _safe_owner_public_id(owner):
    if isinstance(owner, Listing):
        return owner.listing_id
    if isinstance(owner, PropertyRecord):
        return owner.property_id
    if isinstance(owner, SiteCapture):
        return owner.capture_id
    return ""


def _safe_owner_audit_state(owner):
    state = {
        "owner_type": _safe_owner_label(owner),
        "owner_id": _safe_owner_public_id(owner),
    }
    if isinstance(owner, SiteCapture):
        state["capture_id"] = owner.capture_id
        state["property_id"] = str(owner.property_id)
    return state


def _audit_upload(*, actor, media, owner, request=None):
    create_audit_log(
        actor=actor,
        action=MEDIA_UPLOADED,
        entity_type="Media",
        entity_id=media.pk,
        before={},
        after={
            "media_id": media.media_id,
            **_safe_owner_audit_state(owner),
            "source": media.source,
            "mime_type": media.mime_type,
            "variants": sorted(media.variants.values_list("kind", flat=True)),
        },
        request=request,
    )


def _audit_delete(*, actor, media, owner, request=None):
    create_audit_log(
        actor=actor,
        action=MEDIA_DELETED,
        entity_type="Media",
        entity_id=media.pk,
        before={},
        after={
            "media_id": media.media_id,
            **_safe_owner_audit_state(owner),
            "source": media.source,
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


def _normalize_captured_location(value):
    if value is None:
        return None
    if isinstance(value, Point):
        if value.empty:
            raise ValidationError({"captured_location": "Captured location must not be empty."})
        if value.srid != 4326:
            raise ValidationError({"captured_location": "Captured location must use SRID 4326."})
        value = {"type": "Point", "coordinates": [value.x, value.y]}
    elif not isinstance(value, Mapping):
        raise ValidationError({"captured_location": "Captured location must be a GeoJSON Point or SRID 4326 GEOS Point."})

    try:
        return GeoJSONPointField().run_validation(value)
    except ValidationError as exc:
        raise ValidationError({"captured_location": exc.detail}) from exc


def _create_image_media_for_owner(
    *,
    actor,
    owner,
    image,
    source,
    captured_at=None,
    captured_location=None,
    device="",
    request=None,
):
    processed = validate_and_process_image_upload(image)
    captured_location = _normalize_captured_location(captured_location)
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
        )
        stored_keys.append(display_key)
        from apps.payments.documents import pending_objects
        pending = pending_objects.get()
        if pending is not None:
            pending.extend((storage, key) for key in stored_keys)

        content_type = ContentType.objects.get_for_model(owner)
        media = Media(
            media_id=media_id,
            content_type=content_type,
            object_id=owner.pk,
            uploaded_by=actor,
            file_key=original_key,
            source=source,
            captured_at=captured_at,
            captured_location=captured_location,
            device=device,
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


@transaction.atomic
def create_image_media(*, actor, owner_type, owner_id, image, source=Media.Source.UPLOAD, request=None):
    actor = _active_actor(actor)
    owner_type, owner = _resolve_owner(owner_type=owner_type, owner_id=owner_id)
    _ensure_can_upload(actor, owner)
    if source not in {choice.value for choice in Media.Source}:
        raise ValidationError({"source": "Unsupported media source."})
    if source != Media.Source.UPLOAD:
        raise ValidationError({"source": "Only standard upload source is supported for this workflow."})

    return _create_image_media_for_owner(
        actor=actor,
        owner=owner,
        image=image,
        source=source,
        request=request,
    )


def _resolve_site_capture_for_media(site_capture):
    capture_id = getattr(site_capture, "pk", site_capture)
    try:
        return SiteCapture.objects.select_for_update().select_related("property").get(pk=capture_id)
    except (TypeError, ValueError, SiteCapture.DoesNotExist) as exc:
        raise NotFound("Site capture was not found.") from exc


def _ensure_can_manage_site_capture_media(actor, site_capture):
    from apps.site_capture.services import _ensure_can_edit_capture
    _ensure_can_edit_capture(actor, site_capture)
    if site_capture.status != SiteCapture.Status.DRAFT:
        raise ValidationError({"status": "Media can only be changed while the site capture is a draft."})


def upload_site_capture_image(*, site_capture, actor, image, captured_at=None, captured_location=None, device="", request=None):
    from apps.verification.task_services import private_write_scope
    from apps.site_capture.evidence import image_metadata, provenance_flags
    from apps.site_capture.models import CaptureAsset
    from django.conf import settings
    with private_write_scope(), transaction.atomic():
        actor = _active_actor(actor)
        site_capture = _resolve_site_capture_for_media(site_capture)
        _ensure_can_manage_site_capture_media(actor, site_capture)
        # Preserve the legacy endpoint's metadata while giving file metadata priority.
        content = image.read(settings.MEDIA_MAX_UPLOAD_BYTES + 1)
        image.seek(0)
        try:
            file_location, file_time = image_metadata(content)
        except (OSError, ValueError, TypeError) as exc:
            raise ValidationError("Invalid capture image.") from exc
        media = _create_image_media_for_owner(actor=actor, owner=site_capture, image=image, source=Media.Source.SITE_CAPTURE, captured_at=file_time or captured_at, captured_location=file_location or captured_location, device=device, request=request)
        flags, distance = provenance_flags(location=file_location, captured_at=file_time, capture=site_capture)
        CaptureAsset.objects.create(capture=site_capture, media=media, source="UPLOAD", flags=flags, distance_m=distance)
        return media


@transaction.atomic
def remove_site_capture_media(*, site_capture, media, actor, request=None):
    actor = _active_actor(actor)
    site_capture = _resolve_site_capture_for_media(site_capture)
    _ensure_can_manage_site_capture_media(actor, site_capture)
    media_id = getattr(media, "media_id", media)
    capture_content_type = ContentType.objects.get_for_model(SiteCapture)
    try:
        media = (
            Media.objects.select_for_update()
            .prefetch_related("variants")
            .get(media_id=media_id, content_type=capture_content_type, object_id=site_capture.pk)
        )
    except Media.DoesNotExist as exc:
        raise NotFound("Site capture media was not found.") from exc

    variant_keys = list(dict.fromkeys([media.file_key, *media.variants.values_list("file_key", flat=True)]))
    storage = get_private_media_storage()
    _audit_delete(actor=actor, media=media, owner=site_capture, request=request)
    from apps.site_capture.models import CaptureAsset
    CaptureAsset.objects.filter(media=media).delete()
    media.delete()
    transaction.on_commit(lambda: _cleanup(storage, variant_keys))


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
