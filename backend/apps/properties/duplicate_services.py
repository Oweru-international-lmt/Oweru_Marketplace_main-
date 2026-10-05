from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, connection, transaction
from django.db import models
from django.db.models import BooleanField
from django.db.models.expressions import RawSQL
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.services import create_audit_log
from apps.roles.catalog import ROLE_MANAGEMENT
from apps.roles.services import user_has_role

from .audit_events import (
    PROPERTY_DUPLICATE_CONFIRMED,
    PROPERTY_DUPLICATE_DETECTED,
    PROPERTY_DUPLICATE_DISMISSED,
)
from .models import PossibleDuplicate, PropertyRecord
from .policies import get_active_persisted_actor


REVIEWED_STATUSES = frozenset({
    PossibleDuplicate.Status.CONFIRMED_DUPLICATE,
    PossibleDuplicate.Status.NOT_DUPLICATE,
})


def _persisted_property(property_record):
    record_id = getattr(property_record, "pk", property_record)
    if not record_id:
        raise ValidationError({"property": "A persisted PropertyRecord is required."})
    try:
        return PropertyRecord.objects.select_for_update().get(pk=record_id)
    except (TypeError, ValueError, DjangoValidationError, PropertyRecord.DoesNotExist) as exc:
        raise ValidationError({"property": "A persisted PropertyRecord is required."}) from exc


def canonical_property_pair(property_a, property_b):
    first = _persisted_property(property_a)
    second = _persisted_property(property_b)
    if first.pk == second.pk:
        raise ValidationError({"property_b": "A property cannot be a possible duplicate of itself."})
    if str(first.pk) > str(second.pk):
        first, second = second, first
    return first, second


def normalize_signals(signals):
    if not isinstance(signals, (list, tuple, set)) or not signals:
        raise ValidationError({"signals": "At least one duplicate signal is required."})
    normalized = []
    for signal in signals:
        if signal not in PossibleDuplicate.ALLOWED_SIGNALS:
            raise ValidationError({"signals": "Signals must use known duplicate signal codes."})
        if signal not in normalized:
            normalized.append(signal)
    if not normalized:
        raise ValidationError({"signals": "At least one duplicate signal is required."})
    return sorted(normalized)


def _validate_metric(name, value):
    if value is not None and value < 0:
        raise ValidationError({name: "Value must be non-negative."})
    return value


def size_difference_percent(size_a, size_b):
    """Symmetric size delta: abs(a - b) / max(a, b) * 100."""
    first = Decimal(size_a)
    second = Decimal(size_b)
    denominator = max(first, second)
    if denominator <= 0:
        raise ValidationError({"stated_size": "Property sizes must be positive."})
    return ((abs(first - second) / denominator) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _distance_meters(value):
    meters = value.m if hasattr(value, "m") else value
    return Decimal(str(meters)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _persisted_subject_property(property_record):
    record_id = getattr(property_record, "pk", property_record)
    if not record_id:
        raise ValidationError({"property_record": "A persisted PropertyRecord is required."})
    try:
        return PropertyRecord.objects.get(pk=record_id)
    except (TypeError, ValueError, DjangoValidationError, PropertyRecord.DoesNotExist) as exc:
        raise ValidationError({"property_record": "A persisted PropertyRecord is required."}) from exc


def _canonical_sha256_hash(value):
    normalized = (value or "").strip().lower()
    if len(normalized) != 64:
        return ""
    if any(character not in "0123456789abcdef" for character in normalized):
        return ""
    return normalized


def _nearby_property_records(subject, distance_threshold):
    queryset = PropertyRecord.objects.exclude(pk=subject.pk).select_related("created_by")
    if connection.vendor == "postgresql":
        return (
            queryset.annotate(
                is_within_duplicate_distance=RawSQL(
                    (
                        'ST_DWithin("properties_propertyrecord"."pin"::geography, '
                        "ST_GeomFromWKB(%s, 4326)::geography, %s)"
                    ),
                    (bytes(subject.pin.wkb), float(distance_threshold)),
                    output_field=BooleanField(),
                ),
                distance_to_subject=Distance("pin", subject.pin, spheroid=True),
            )
            .filter(is_within_duplicate_distance=True)
            .order_by("pk")
        )
    return (
        queryset.filter(pin__distance_lte=(subject.pin, D(m=distance_threshold)))
        .annotate(distance_to_subject=Distance("pin", subject.pin, spheroid=True))
        .order_by("pk")
    )


def _persisted_listing_photo(listing_photo):
    from apps.listings.models import ListingPhoto

    photo_id = getattr(listing_photo, "pk", listing_photo)
    if not photo_id:
        raise ValidationError({"listing_photo": "A persisted ListingPhoto is required."})
    try:
        return (
            ListingPhoto.objects.select_related("listing__property", "media", "media__content_type")
            .prefetch_related("media__variants")
            .get(pk=photo_id)
        )
    except (TypeError, ValueError, DjangoValidationError, ListingPhoto.DoesNotExist) as exc:
        raise ValidationError({"listing_photo": "A persisted ListingPhoto is required."}) from exc


def _is_valid_photo_duplicate_source(listing_photo):
    from apps.listings.models import Listing
    from apps.media.models import MediaVariant

    media = listing_photo.media
    listing = listing_photo.listing
    listing_content_type = ContentType.objects.get_for_model(Listing)
    return (
        media.content_type_id == listing_content_type.pk
        and media.object_id == listing.pk
        and media.mime_type in set(settings.MEDIA_ALLOWED_IMAGE_MIME_TYPES)
        and {MediaVariant.Kind.ORIGINAL, MediaVariant.Kind.DISPLAY}.issubset(
            set(media.variants.values_list("kind", flat=True))
        )
    )


def _photo_duplicate_matches(*, listing_photo, file_hash):
    from apps.listings.models import Listing, ListingPhoto
    from apps.media.models import MediaVariant

    listing_content_type = ContentType.objects.get_for_model(Listing)
    return (
        ListingPhoto.objects.exclude(pk=listing_photo.pk)
        .select_related("listing__property", "media")
        .filter(
            media__file_hash=file_hash,
            media__content_type=listing_content_type,
            media__object_id=models.F("listing_id"),
            media__mime_type__in=set(settings.MEDIA_ALLOWED_IMAGE_MIME_TYPES),
        )
        .filter(media__variants__kind=MediaVariant.Kind.ORIGINAL)
        .filter(media__variants__kind=MediaVariant.Kind.DISPLAY)
        .exclude(listing__property=listing_photo.listing.property)
        .order_by("listing__property_id", "pk")
        .distinct()
    )


def detect_photo_duplicates_for_listing_photo(*, listing_photo, request=None):
    listing_photo = _persisted_listing_photo(listing_photo)
    file_hash = _canonical_sha256_hash(listing_photo.media.file_hash)
    if not file_hash or not _is_valid_photo_duplicate_source(listing_photo):
        return []

    subject_property = listing_photo.listing.property
    candidates = []
    seen_property_ids = set()
    for matching_photo in _photo_duplicate_matches(listing_photo=listing_photo, file_hash=file_hash):
        other_property = matching_photo.listing.property
        if other_property.pk in seen_property_ids:
            continue
        seen_property_ids.add(other_property.pk)
        candidates.append(
            record_possible_duplicate(
                property_a=subject_property,
                property_b=other_property,
                signals=[PossibleDuplicate.SIGNAL_PHOTO_SIMILARITY],
                request=request,
            )
        )
    return candidates


def detect_property_duplicates(*, property_record, request=None):
    subject = _persisted_subject_property(property_record)
    distance_threshold = settings.PROPERTY_DUPLICATE_DISTANCE_METERS
    size_threshold = Decimal(str(settings.PROPERTY_DUPLICATE_SIZE_DIFFERENCE_PERCENT))
    nearby_records = _nearby_property_records(subject, distance_threshold)

    candidates = []
    for nearby in nearby_records:
        distance_meters = _distance_meters(nearby.distance_to_subject)
        size_difference = size_difference_percent(subject.stated_size, nearby.stated_size)
        signals = [PossibleDuplicate.SIGNAL_PIN_PROXIMITY]
        if size_difference <= size_threshold:
            signals.append(PossibleDuplicate.SIGNAL_SIZE_SIMILARITY)
        candidates.append(
            record_possible_duplicate(
                property_a=subject,
                property_b=nearby,
                signals=signals,
                distance_meters=distance_meters,
                size_difference_percent=size_difference,
                request=request,
            )
        )
    return candidates


def _audit_duplicate_detected(*, possible_duplicate, added_signals, request=None):
    create_audit_log(
        actor=None,
        action=PROPERTY_DUPLICATE_DETECTED,
        entity_type="PossibleDuplicate",
        entity_id=possible_duplicate.pk,
        before={},
        after={
            "possible_duplicate_id": str(possible_duplicate.pk),
            "property_a_id": possible_duplicate.property_a.property_id,
            "property_b_id": possible_duplicate.property_b.property_id,
            "signals": sorted(added_signals),
            "status": possible_duplicate.status,
        },
        request=request,
    )


def _audit_duplicate_reviewed(*, actor, possible_duplicate, action, request=None):
    create_audit_log(
        actor=actor,
        action=action,
        entity_type="PossibleDuplicate",
        entity_id=possible_duplicate.pk,
        before={},
        after={
            "possible_duplicate_id": str(possible_duplicate.pk),
            "property_a_id": possible_duplicate.property_a.property_id,
            "property_b_id": possible_duplicate.property_b.property_id,
            "signals": sorted(possible_duplicate.signals),
            "status": possible_duplicate.status,
        },
        request=request,
    )


@transaction.atomic
def record_possible_duplicate(
    *,
    property_a,
    property_b,
    signals,
    distance_meters=None,
    size_difference_percent=None,
    request=None,
):
    property_a, property_b = canonical_property_pair(property_a, property_b)
    incoming_signals = normalize_signals(signals)
    distance_meters = _validate_metric("distance_meters", distance_meters)
    size_difference_percent = _validate_metric("size_difference_percent", size_difference_percent)

    try:
        possible_duplicate = (
            PossibleDuplicate.objects.select_for_update()
            .select_related("property_a", "property_b")
            .get(property_a=property_a, property_b=property_b)
        )
        created = False
    except PossibleDuplicate.DoesNotExist:
        possible_duplicate = PossibleDuplicate(property_a=property_a, property_b=property_b, signals=incoming_signals)
        created = True

    existing_signals = set(possible_duplicate.signals or [])
    merged_signals = sorted(existing_signals | set(incoming_signals))
    added_signals = sorted(set(incoming_signals) - existing_signals)
    changed_fields = []

    if possible_duplicate.signals != merged_signals:
        possible_duplicate.signals = merged_signals
        changed_fields.append("signals")
    if distance_meters is not None and possible_duplicate.distance_meters != distance_meters:
        possible_duplicate.distance_meters = distance_meters
        changed_fields.append("distance_meters")
    if size_difference_percent is not None and possible_duplicate.size_difference_percent != size_difference_percent:
        possible_duplicate.size_difference_percent = size_difference_percent
        changed_fields.append("size_difference_percent")

    if created:
        try:
            possible_duplicate.full_clean()
            possible_duplicate.save()
        except IntegrityError:
            possible_duplicate = (
                PossibleDuplicate.objects.select_for_update()
                .select_related("property_a", "property_b")
                .get(property_a=property_a, property_b=property_b)
            )
            return record_possible_duplicate(
                property_a=property_a,
                property_b=property_b,
                signals=incoming_signals,
                distance_meters=distance_meters,
                size_difference_percent=size_difference_percent,
                request=request,
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc
        _audit_duplicate_detected(possible_duplicate=possible_duplicate, added_signals=incoming_signals, request=request)
        return possible_duplicate

    if changed_fields:
        try:
            possible_duplicate.full_clean()
            possible_duplicate.save(update_fields=[*changed_fields, "updated_at"])
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc
    if added_signals:
        _audit_duplicate_detected(possible_duplicate=possible_duplicate, added_signals=added_signals, request=request)
    return possible_duplicate


def _active_management_actor(actor):
    persisted = get_active_persisted_actor(actor)
    if persisted is None or not user_has_role(persisted, ROLE_MANAGEMENT):
        raise PermissionDenied("An active Management role is required.")
    return persisted


def _review_note(note):
    if note is None:
        return ""
    return " ".join(str(note).split())[:1000]


def _resolve_possible_duplicate(possible_duplicate):
    duplicate_id = getattr(possible_duplicate, "pk", possible_duplicate)
    try:
        return (
            PossibleDuplicate.objects.select_for_update(of=("self",))
            .select_related("property_a", "property_b", "reviewed_by")
            .get(pk=duplicate_id)
        )
    except (TypeError, ValueError, DjangoValidationError, PossibleDuplicate.DoesNotExist) as exc:
        raise ValidationError({"possible_duplicate": "A valid possible duplicate is required."}) from exc


def _set_review_status(*, actor, possible_duplicate, status, audit_action, review_note="", request=None):
    actor = _active_management_actor(actor)
    possible_duplicate = _resolve_possible_duplicate(possible_duplicate)

    if possible_duplicate.status != PossibleDuplicate.Status.PENDING:
        raise ValidationError({"status": "Reviewed duplicate decisions cannot be changed in this workflow."})

    possible_duplicate.status = status
    possible_duplicate.reviewed_by = actor
    possible_duplicate.reviewed_at = timezone.now()
    possible_duplicate.review_note = _review_note(review_note)
    try:
        possible_duplicate.full_clean()
        possible_duplicate.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note", "updated_at"])
    except DjangoValidationError as exc:
        raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc
    _audit_duplicate_reviewed(actor=actor, possible_duplicate=possible_duplicate, action=audit_action, request=request)
    return possible_duplicate


@transaction.atomic
def confirm_possible_duplicate(*, actor, possible_duplicate, review_note="", request=None):
    return _set_review_status(
        actor=actor,
        possible_duplicate=possible_duplicate,
        status=PossibleDuplicate.Status.CONFIRMED_DUPLICATE,
        audit_action=PROPERTY_DUPLICATE_CONFIRMED,
        review_note=review_note,
        request=request,
    )


@transaction.atomic
def dismiss_possible_duplicate(*, actor, possible_duplicate, review_note="", request=None):
    return _set_review_status(
        actor=actor,
        possible_duplicate=possible_duplicate,
        status=PossibleDuplicate.Status.NOT_DUPLICATE,
        audit_action=PROPERTY_DUPLICATE_DISMISSED,
        review_note=review_note,
        request=request,
    )
