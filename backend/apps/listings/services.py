import logging
import secrets

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.audit.services import create_audit_log
from apps.media.models import Media, MediaVariant
from apps.media.storage import get_private_media_storage
from apps.properties.duplicate_services import detect_photo_duplicates_for_listing_photo
from apps.properties.models import PropertyRecord

from apps.lister_identity.models import ListerIdentity
from apps.lister_identity.services import is_lister_identity_verified

from .lifecycle import (
    ActivationRequirement,
    activation_eligibility_from_requirements,
    is_transition_documented,
)
from .audit_events import (
    LISTING_ACTIVATED,
    LISTING_CREATED,
    LISTING_RESTORED,
    LISTING_SUSPENDED,
    LISTING_UPDATED,
    LISTING_WITHDRAWN,
)
from .audit_photo_events import LISTING_PHOTO_ADDED, LISTING_PHOTO_REMOVED, LISTING_PHOTOS_REORDERED
from .models import Listing, ListingPhoto
from . import policies


LISTING_ID_PREFIX = "LST"
LISTING_ID_TOKEN_BYTES = 8
LISTING_ID_MAX_ATTEMPTS = 8
LISTING_MINIMUM_PHOTOS = 3
PUBLIC_LISTING_STATUSES = frozenset({
    Listing.Status.ACTIVE,
    Listing.Status.UNDER_OFFER,
})
PUBLIC_PHOTO_NOT_FOUND_MESSAGE = "Public photo was not found."
logger = logging.getLogger(__name__)

LISTING_MUTABLE_FIELDS = frozenset({"selling_price", "owner_price", "description", "features"})
LISTING_SERVER_FIELDS = frozenset({
    "id",
    "listing_id",
    "property",
    "property_id",
    "lister",
    "lister_id",
    "lister_kind",
    "currency",
    "status",
    "created_at",
    "updated_at",
})
LISTING_UNSUPPORTED_FIELDS = frozenset({
    "owner_name",
    "owner_phone",
    "owner_whatsapp",
    "owner_bank_account",
    "phone_confirmed",
    "verification_level",
    "is_verified",
    "published_at",
    "promotion",
    "is_promoted",
    "photos",
    "media",
    "duplicate_status",
    "commission",
    "commission_rate",
    "lead",
    "deal",
    "transaction",
    "payment",
})


def _listing_id_token():
    return secrets.token_hex(LISTING_ID_TOKEN_BYTES).upper()


def generate_listing_id():
    for _ in range(LISTING_ID_MAX_ATTEMPTS):
        candidate = f"{LISTING_ID_PREFIX}-{_listing_id_token()}"
        if not Listing.objects.filter(listing_id=candidate).exists():
            return candidate
    raise ValidationError({"listing_id": "Could not generate a unique listing identifier."})


def _active_persisted_actor(actor):
    persisted = policies.get_active_persisted_actor(actor)
    if persisted is None:
        raise PermissionDenied("An active persisted account is required.")
    return persisted


def _ensure_can_create_listing(actor, lister_kind):
    if policies.role_code_for_lister_kind(lister_kind) is None:
        raise ValidationError({"lister_kind": "A valid lister kind is required."})
    if not policies.can_create_listing(actor, lister_kind=lister_kind):
        raise PermissionDenied("An active matching lister role is required.")


def _resolve_property_record(property_record):
    record_id = getattr(property_record, "pk", property_record)
    if not record_id:
        raise ValidationError({"property_record": "A persisted property record is required."})
    try:
        return PropertyRecord.objects.select_related("created_by").get(pk=record_id)
    except (TypeError, ValueError, DjangoValidationError, PropertyRecord.DoesNotExist) as exc:
        raise ValidationError({"property_record": "A valid property record is required."}) from exc


def _ensure_can_create_against_property(actor, property_record):
    if not policies.can_create_listing_for_property(actor, property_record):
        raise PermissionDenied("You cannot create a listing for this property record.")


def _clean_create_attrs(attrs):
    protected = LISTING_SERVER_FIELDS.intersection(attrs)
    if protected:
        raise ValidationError({field: "This field is server-controlled." for field in sorted(protected)})

    unsupported = (set(attrs) - LISTING_MUTABLE_FIELDS) | LISTING_UNSUPPORTED_FIELDS.intersection(attrs)
    if unsupported:
        raise ValidationError({field: "This field is not supported for listings." for field in sorted(unsupported)})

    return {field: attrs[field] for field in LISTING_MUTABLE_FIELDS if field in attrs}


def _clean_update_attrs(attrs):
    protected = LISTING_SERVER_FIELDS.intersection(attrs)
    if protected:
        raise ValidationError({field: "This field is immutable." for field in sorted(protected)})

    unsupported = (set(attrs) - LISTING_MUTABLE_FIELDS) | LISTING_UNSUPPORTED_FIELDS.intersection(attrs)
    if unsupported:
        raise ValidationError({field: "This field is not supported for listings." for field in sorted(unsupported)})

    return {field: attrs[field] for field in LISTING_MUTABLE_FIELDS if field in attrs}


def _validate_listing(listing):
    try:
        listing.full_clean()
    except DjangoValidationError as exc:
        raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc


def _listing_field_value(listing, field):
    return getattr(listing, field)


def _effective_changed_fields(listing, values):
    return {field for field, value in values.items() if _listing_field_value(listing, field) != value}


def _listing_audit_identifiers(listing):
    return {
        "listing_id": listing.listing_id,
        "property_id": listing.property.property_id,
    }


def _listing_created_state(listing):
    return {
        **_listing_audit_identifiers(listing),
        "lister_kind": listing.lister_kind,
        "status": listing.status,
    }


def _listing_transition_state(listing, *, from_status, to_status, **extra):
    return {
        "listing_id": listing.listing_id,
        "from_status": from_status,
        "to_status": to_status,
        **extra,
    }


def _audit_listing(*, actor, action, listing, before=None, after=None, request=None):
    return create_audit_log(
        actor=actor,
        action=action,
        entity_type="Listing",
        entity_id=listing.pk,
        before=before or {},
        after=after or {},
        request=request,
    )


def _resolve_listing_for_update(listing):
    listing_pk = getattr(listing, "pk", listing)
    try:
        return Listing.objects.select_for_update().select_related("lister", "property").get(pk=listing_pk)
    except (TypeError, ValueError, DjangoValidationError, Listing.DoesNotExist) as exc:
        raise NotFound("Listing was not found.") from exc


def _ensure_can_update_listing(actor, listing):
    if not policies.can_update_listing(actor, listing):
        raise PermissionDenied("You cannot update this listing.")


def _ensure_can_manage_listing_photos(actor, listing):
    _ensure_can_update_listing(actor, listing)
    if listing.status != Listing.Status.DRAFT:
        raise ValidationError({"status": "Listing photos can only be managed while the listing is in draft."})


def _ensure_can_activate_listing(actor, listing):
    if not policies.can_activate_listing(actor, listing):
        raise PermissionDenied("You cannot activate this listing.")


def _ensure_can_withdraw_listing(actor, listing):
    if not policies.can_withdraw_listing(actor, listing):
        raise PermissionDenied("You cannot withdraw this listing.")


def _ensure_can_suspend_listing(actor, listing):
    if not policies.can_suspend_listing(actor, listing):
        raise PermissionDenied("An active Management role is required.")


def _ensure_can_restore_listing(actor, listing):
    if not policies.can_restore_listing(actor, listing):
        raise PermissionDenied("An active Management role is required.")


def _ensure_documented_transition(listing, target_status):
    if not is_transition_documented(listing.status, target_status):
        raise ValidationError({"status": "This listing status transition is not allowed."})


def _set_listing_status(listing, target_status, *, actor, action, request=None, after_extra=None):
    from_status = listing.status
    listing.status = target_status
    _validate_listing(listing)
    listing.save(update_fields=["status", "updated_at"])
    _audit_listing(
        actor=actor,
        action=action,
        listing=listing,
        after=_listing_transition_state(
            listing,
            from_status=from_status,
            to_status=target_status,
            **(after_extra or {}),
        ),
        request=request,
    )
    return listing


def _verified_lister_identity_requirement(listing):
    try:
        identity = ListerIdentity.objects.select_related("user").get(user=listing.lister)
    except ListerIdentity.DoesNotExist:
        return ActivationRequirement("lister_identity_verified", "UNSATISFIED")
    status = "SATISFIED" if is_lister_identity_verified(identity) else "UNSATISFIED"
    return ActivationRequirement("lister_identity_verified", status)


def _phone_confirmation_requirement(listing):
    from apps.payments.models import PhoneConfirmation
    confirmed = PhoneConfirmation.objects.filter(user_id=listing.lister_id, phone=listing.lister.phone).exists()
    return ActivationRequirement("lister_phone_confirmed", "SATISFIED" if confirmed else "UNAVAILABLE")


def _listing_media_requirement(listing):
    status = "SATISFIED" if is_listing_media_ready(listing) else "UNSATISFIED"
    return ActivationRequirement("listing_required_media", status)


def check_listing_activation_eligibility(*, listing):
    phone = _phone_confirmation_requirement(listing)
    financial_requirements = ()
    if phone.status == "SATISFIED":
        financial_requirements = (ActivationRequirement("listing_frozen_rate_version", "SATISFIED" if listing.rate_table_id else "UNSATISFIED"),)
    return activation_eligibility_from_requirements((
        _verified_lister_identity_requirement(listing),
        _listing_media_requirement(listing),
        phone,
        *financial_requirements,
    ))


def _ensure_activation_eligible(listing):
    eligibility = check_listing_activation_eligibility(listing=listing)
    if not eligibility.is_eligible:
        raise ValidationError({"activation": list(eligibility.blocked_codes)})
    return eligibility


@transaction.atomic
def create_listing(
    *,
    actor,
    property_record,
    lister_kind,
    selling_price,
    owner_price,
    description="",
    features=None,
    request=None,
    **attrs,
):
    actor = _active_persisted_actor(actor)
    _ensure_can_create_listing(actor, lister_kind)
    property_record = _resolve_property_record(property_record)
    _ensure_can_create_against_property(actor, property_record)
    from apps.commissions.services import current_rate_table, lock_rate_publication
    lock_rate_publication()
    frozen_table = current_rate_table()
    if actor.has_marketplace_permission("listing.create") and frozen_table is None:
        raise ValidationError("Publish a commission rate table before creating a financial-workflow Listing.")

    values = _clean_create_attrs(attrs)
    values.update({
        "selling_price": selling_price,
        "owner_price": owner_price,
        "description": description,
        "features": [] if features is None else features,
    })

    for _ in range(LISTING_ID_MAX_ATTEMPTS):
        listing = Listing(
            listing_id=generate_listing_id(),
            property=property_record,
            lister=actor,
            lister_kind=lister_kind,
            currency=Listing.Currency.TZS,
            status=Listing.Status.DRAFT,
            rate_table=frozen_table,
            **values,
        )
        _validate_listing(listing)
        try:
            with transaction.atomic():
                listing.save()
                _audit_listing(
                    actor=actor,
                    action=LISTING_CREATED,
                    listing=listing,
                    after=_listing_created_state(listing),
                    request=request,
                )
            return listing
        except IntegrityError as exc:
            if "listing_id" not in str(exc).lower():
                raise

    raise ValidationError({"listing_id": "Could not create a unique listing identifier."})


def get_listing(*, actor, listing_id):
    actor = _active_persisted_actor(actor)
    try:
        listing = Listing.objects.select_related("property", "lister").get(listing_id=listing_id)
    except Listing.DoesNotExist as exc:
        raise NotFound("Listing was not found.") from exc

    if policies.can_view_listing(actor, listing):
        return listing
    raise PermissionDenied("You do not have access to this listing.")


@transaction.atomic
def update_listing(*, actor, listing, request=None, **changes):
    actor = _active_persisted_actor(actor)
    values = _clean_update_attrs(changes)

    locked = _resolve_listing_for_update(listing)

    if locked.status != Listing.Status.DRAFT:
        raise PermissionDenied("Only draft listings can be updated.")
    _ensure_can_update_listing(actor, locked)

    changed_fields = _effective_changed_fields(locked, values)
    for field, value in values.items():
        setattr(locked, field, value)
    _validate_listing(locked)
    if changed_fields:
        locked.save(update_fields=[*changed_fields, "updated_at"])
        _audit_listing(
            actor=actor,
            action=LISTING_UPDATED,
            listing=locked,
            after={
                "listing_id": locked.listing_id,
                "changed_fields": sorted(changed_fields),
            },
            request=request,
        )
    return locked


def _listing_content_type():
    return ContentType.objects.get_for_model(Listing)


def _media_belongs_to_listing(media, listing):
    return (
        isinstance(media, Media)
        and media.content_type_id == _listing_content_type().pk
        and media.object_id == listing.pk
    )


def _media_has_required_variants(media):
    existing_variants = set(media.variants.values_list("kind", flat=True))
    return {MediaVariant.Kind.ORIGINAL, MediaVariant.Kind.DISPLAY}.issubset(existing_variants)


def _is_valid_listing_photo(photo):
    media = photo.media
    return (
        _media_belongs_to_listing(media, photo.listing)
        and media.mime_type in set(settings.MEDIA_ALLOWED_IMAGE_MIME_TYPES)
        and _media_has_required_variants(media)
    )


def is_listing_media_ready(listing):
    listing_id = getattr(listing, "pk", listing)
    if not listing_id:
        return False
    valid_count = 0
    photos = ListingPhoto.objects.select_related("listing", "media", "media__content_type").filter(listing_id=listing_id)
    seen_media_ids = set()
    for photo in photos:
        if photo.media_id in seen_media_ids:
            continue
        if _is_valid_listing_photo(photo):
            seen_media_ids.add(photo.media_id)
            valid_count += 1
        if valid_count >= LISTING_MINIMUM_PHOTOS:
            return True
    return False


def _resolve_media(media):
    media_id = getattr(media, "pk", media)
    try:
        return Media.objects.select_related("content_type").prefetch_related("variants").get(pk=media_id)
    except (TypeError, ValueError, DjangoValidationError, Media.DoesNotExist) as exc:
        raise NotFound("Media was not found.") from exc


def _validate_listing_photo_media(*, listing, media):
    if not _media_belongs_to_listing(media, listing):
        raise ValidationError({"media_id": "Media must belong to this listing."})
    if media.mime_type not in set(settings.MEDIA_ALLOWED_IMAGE_MIME_TYPES):
        raise ValidationError({"media_id": "Media must be a supported image."})
    if not _media_has_required_variants(media):
        raise ValidationError({"media_id": "Media must have original and display variants."})


def _listing_photo_audit_state(listing_photo):
    return {
        "listing_id": listing_photo.listing.listing_id,
        "media_id": listing_photo.media.media_id,
        "position": listing_photo.position,
    }


def _audit_listing_photo_added(*, actor, listing_photo, request=None):
    create_audit_log(
        actor=actor,
        action=LISTING_PHOTO_ADDED,
        entity_type="ListingPhoto",
        entity_id=listing_photo.pk,
        before={},
        after={
            **_listing_photo_audit_state(listing_photo),
            "photo_count": ListingPhoto.objects.filter(listing=listing_photo.listing).count(),
        },
        request=request,
    )


def _audit_listing_photo_removed(*, actor, listing, listing_photo_state, photo_count, request=None):
    create_audit_log(
        actor=actor,
        action=LISTING_PHOTO_REMOVED,
        entity_type="ListingPhoto",
        entity_id=listing_photo_state["id"],
        before=listing_photo_state,
        after={
            "listing_id": listing.listing_id,
            "photo_count": photo_count,
        },
        request=request,
    )


def _audit_listing_photos_reordered(*, actor, listing, ordered_photo_ids, request=None):
    create_audit_log(
        actor=actor,
        action=LISTING_PHOTOS_REORDERED,
        entity_type="Listing",
        entity_id=listing.pk,
        before={},
        after={
            "listing_id": listing.listing_id,
            "photo_count": len(ordered_photo_ids),
            "ordered_photo_ids": [str(photo_id) for photo_id in ordered_photo_ids],
        },
        request=request,
    )


def _run_photo_duplicate_detection(listing_photo, *, request=None):
    try:
        return detect_photo_duplicates_for_listing_photo(listing_photo=listing_photo, request=request)
    except ValidationError as exc:
        logger.warning(
            "Advisory listing photo duplicate detection skipped.",
            extra={"listing_photo_id": str(listing_photo.pk), "error": str(exc.detail)},
        )
        return []


@transaction.atomic
def add_listing_photo(*, actor, listing, media, position=None, request=None):
    actor = _active_persisted_actor(actor)
    listing = _resolve_listing_for_update(listing)
    _ensure_can_manage_listing_photos(actor, listing)
    media = _resolve_media(media)
    _validate_listing_photo_media(listing=listing, media=media)

    if ListingPhoto.objects.filter(listing=listing, media=media).exists():
        raise ValidationError({"media_id": "Media is already associated with this listing."})

    locked_photos = list(ListingPhoto.objects.select_for_update().filter(listing=listing).order_by("position"))
    if position is None:
        position = (max((photo.position for photo in locked_photos), default=-1) + 1)
    if position < 0:
        raise ValidationError({"position": "Position must be non-negative."})
    if any(photo.position == position for photo in locked_photos):
        raise ValidationError({"position": "Position is already used for this listing."})

    listing_photo = ListingPhoto(listing=listing, media=media, position=position)
    try:
        listing_photo.full_clean()
        listing_photo.save()
    except DjangoValidationError as exc:
        raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc
    except IntegrityError as exc:
        raise ValidationError({"photo": "Listing photo association could not be created."}) from exc
    _audit_listing_photo_added(actor=actor, listing_photo=listing_photo, request=request)
    _run_photo_duplicate_detection(listing_photo, request=request)
    return listing_photo


@transaction.atomic
def remove_listing_photo(*, actor, listing, listing_photo, request=None):
    actor = _active_persisted_actor(actor)
    listing = _resolve_listing_for_update(listing)
    _ensure_can_manage_listing_photos(actor, listing)
    photo_id = getattr(listing_photo, "pk", listing_photo)
    try:
        photo = ListingPhoto.objects.select_for_update().select_related("listing", "media").get(pk=photo_id, listing=listing)
    except (TypeError, ValueError, DjangoValidationError, ListingPhoto.DoesNotExist) as exc:
        raise NotFound("Listing photo was not found.") from exc

    state = {**_listing_photo_audit_state(photo), "id": str(photo.pk)}
    photo.delete()
    _audit_listing_photo_removed(
        actor=actor,
        listing=listing,
        listing_photo_state=state,
        photo_count=ListingPhoto.objects.filter(listing=listing).count(),
        request=request,
    )


@transaction.atomic
def reorder_listing_photos(*, actor, listing, ordered_photo_ids, request=None):
    actor = _active_persisted_actor(actor)
    listing = _resolve_listing_for_update(listing)
    _ensure_can_manage_listing_photos(actor, listing)
    if not isinstance(ordered_photo_ids, (list, tuple)):
        raise ValidationError({"photo_ids": "Photo IDs must be supplied as a list."})

    requested = [str(photo_id) for photo_id in ordered_photo_ids]
    if len(requested) != len(set(requested)):
        raise ValidationError({"photo_ids": "Photo IDs must not contain duplicates."})

    photos = list(ListingPhoto.objects.select_for_update().filter(listing=listing).order_by("position"))
    existing_ids = {str(photo.pk) for photo in photos}
    requested_ids = set(requested)
    if requested_ids != existing_ids:
        raise ValidationError({"photo_ids": "Photo IDs must exactly match current listing photos."})

    photos_by_id = {str(photo.pk): photo for photo in photos}
    offset = max((photo.position for photo in photos), default=-1) + len(photos) + 1000
    for index, photo in enumerate(photos):
        photo.position = offset + index
        photo.save(update_fields=["position", "updated_at"])
    for index, photo_id in enumerate(requested):
        photo = photos_by_id[photo_id]
        photo.position = index
        photo.save(update_fields=["position", "updated_at"])

    _audit_listing_photos_reordered(actor=actor, listing=listing, ordered_photo_ids=requested, request=request)
    return list(ListingPhoto.objects.filter(listing=listing).order_by("position"))


@transaction.atomic
def activate_listing(*, actor, listing, request=None):
    actor = _active_persisted_actor(actor)
    locked = _resolve_listing_for_update(listing)
    _ensure_can_activate_listing(actor, locked)
    if locked.status == Listing.Status.SUSPENDED:
        raise PermissionDenied("Suspended listings require Management restoration.")
    _ensure_documented_transition(locked, Listing.Status.ACTIVE)
    _ensure_activation_eligible(locked)
    return _set_listing_status(locked, Listing.Status.ACTIVE, actor=actor, action=LISTING_ACTIVATED, request=request)


@transaction.atomic
def withdraw_listing(*, actor, listing, request=None):
    actor = _active_persisted_actor(actor)
    locked = _resolve_listing_for_update(listing)
    _ensure_can_withdraw_listing(actor, locked)
    _ensure_documented_transition(locked, Listing.Status.WITHDRAWN)
    return _set_listing_status(locked, Listing.Status.WITHDRAWN, actor=actor, action=LISTING_WITHDRAWN, request=request)


@transaction.atomic
def suspend_listing(*, actor, listing, reason, request=None):
    actor = _active_persisted_actor(actor)
    if reason is None or not isinstance(reason, str) or not reason.strip():
        raise ValidationError({"reason": "Suspension reason is required."})
    locked = _resolve_listing_for_update(listing)
    _ensure_can_suspend_listing(actor, locked)
    _ensure_documented_transition(locked, Listing.Status.SUSPENDED)
    return _set_listing_status(
        locked,
        Listing.Status.SUSPENDED,
        actor=actor,
        action=LISTING_SUSPENDED,
        request=request,
        after_extra={"reason_present": True},
    )


@transaction.atomic
def restore_listing(*, actor, listing, request=None):
    actor = _active_persisted_actor(actor)
    locked = _resolve_listing_for_update(listing)
    _ensure_can_restore_listing(actor, locked)
    _ensure_documented_transition(locked, Listing.Status.ACTIVE)
    _ensure_activation_eligible(locked)
    return _set_listing_status(locked, Listing.Status.ACTIVE, actor=actor, action=LISTING_RESTORED, request=request)


def get_accessible_listings(actor):
    return policies.get_accessible_listings(actor)


def _public_display_variant_prefetch():
    return Prefetch(
        "media__variants",
        queryset=MediaVariant.objects.filter(kind=MediaVariant.Kind.DISPLAY),
        to_attr="public_display_variants",
    )


def _public_listing_photo_queryset():
    return (
        ListingPhoto.objects.select_related("media", "media__content_type")
        .prefetch_related(_public_display_variant_prefetch())
        .order_by("position", "created_at")
    )


def get_public_listings():
    return (
        Listing.objects.select_related(
            "property",
            "property__region",
            "property__district",
            "property__ward",
            "property__locality",
            "lister",
            "lister__lister_identity",
        )
        .prefetch_related(Prefetch("photos", queryset=_public_listing_photo_queryset(), to_attr="public_photos"))
        .filter(status__in=PUBLIC_LISTING_STATUSES)
        .order_by("-created_at", "-id")
    )


def get_public_listing(*, listing_id):
    try:
        return get_public_listings().get(listing_id=listing_id)
    except Listing.DoesNotExist as exc:
        raise NotFound("Listing was not found.") from exc


def _public_listing_or_404(listing):
    if isinstance(listing, Listing):
        if listing.status in PUBLIC_LISTING_STATUSES:
            return listing
        raise NotFound("Listing was not found.")
    listing_id = getattr(listing, "listing_id", listing)
    return get_public_listing(listing_id=listing_id)


def _display_variant(media):
    prefetched = getattr(media, "public_display_variants", None)
    if prefetched is not None:
        if not prefetched:
            raise NotFound(PUBLIC_PHOTO_NOT_FOUND_MESSAGE)
        return prefetched[0]
    try:
        return media.variants.get(kind=MediaVariant.Kind.DISPLAY)
    except MediaVariant.DoesNotExist as exc:
        raise NotFound(PUBLIC_PHOTO_NOT_FOUND_MESSAGE) from exc


def _ensure_public_photo_association(*, listing, listing_photo):
    if listing_photo.listing_id != listing.pk:
        raise NotFound(PUBLIC_PHOTO_NOT_FOUND_MESSAGE)

    media = listing_photo.media
    listing_content_type = ContentType.objects.get_for_model(Listing)
    if media.content_type_id != listing_content_type.pk or media.object_id != listing.pk:
        raise NotFound(PUBLIC_PHOTO_NOT_FOUND_MESSAGE)


def _public_display_access_for_photo(*, listing, listing_photo):
    _ensure_public_photo_association(listing=listing, listing_photo=listing_photo)
    variant = _display_variant(listing_photo.media)
    try:
        url = get_private_media_storage().generate_signed_read_url(
            key=variant.file_key,
            expires_in=settings.MEDIA_SIGNED_URL_TTL_SECONDS,
        )
    except Exception as exc:
        raise NotFound(PUBLIC_PHOTO_NOT_FOUND_MESSAGE) from exc
    return {
        "position": listing_photo.position,
        "url": url,
    }


def get_public_listing_photo_display_access(*, listing, listing_photo):
    public_listing = _public_listing_or_404(listing)
    photo_id = getattr(listing_photo, "pk", listing_photo)
    try:
        photo = _public_listing_photo_queryset().get(pk=photo_id)
    except (TypeError, ValueError, DjangoValidationError, ListingPhoto.DoesNotExist) as exc:
        raise NotFound(PUBLIC_PHOTO_NOT_FOUND_MESSAGE) from exc
    return _public_display_access_for_photo(listing=public_listing, listing_photo=photo)


def get_public_listing_photo_display_accesses(*, listing):
    public_listing = _public_listing_or_404(listing)
    photos = getattr(listing, "public_photos", None)
    if photos is None:
        photos = _public_listing_photo_queryset().filter(listing=public_listing)

    accesses = []
    for photo in photos:
        try:
            accesses.append(_public_display_access_for_photo(listing=public_listing, listing_photo=photo))
        except NotFound:
            continue
    return accesses
