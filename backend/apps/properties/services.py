import secrets

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.audit.services import create_audit_log
from apps.localities.models import Locality
from apps.localities.services import create_pending_locality

from .audit_events import PROPERTY_CREATED, PROPERTY_UPDATED
from .models import PropertyRecord
from .policies import can_create_property_record, can_update_property_record, can_view_property_record, get_active_persisted_actor


PROPERTY_ID_PREFIX = "OWR"
PROPERTY_ID_TOKEN_BYTES = 8
PROPERTY_ID_MAX_ATTEMPTS = 8

PROPERTY_RECORD_MUTABLE_FIELDS = frozenset({
    "category",
    "pin",
    "boundary",
    "region",
    "district",
    "ward",
    "locality",
    "stated_size",
    "size_unit",
    "title_type",
})
PROPERTY_LOCALITY_INPUT_FIELDS = frozenset({"locality_name", "locality_kind"})
PROPERTY_RECORD_SERVER_FIELDS = frozenset({"id", "property_id", "created_by", "created_at", "updated_at"})
PROPERTY_RECORD_AUDITED_FIELDS = PROPERTY_RECORD_MUTABLE_FIELDS


def _property_id_token():
    return secrets.token_hex(PROPERTY_ID_TOKEN_BYTES).upper()


def generate_property_id():
    for _ in range(PROPERTY_ID_MAX_ATTEMPTS):
        candidate = f"{PROPERTY_ID_PREFIX}-{_property_id_token()}"
        if not PropertyRecord.objects.filter(property_id=candidate).exists():
            return candidate
    raise ValidationError({"property_id": "Could not generate a unique property identifier."})


def _active_persisted_actor(actor):
    persisted = get_active_persisted_actor(actor)
    if persisted is None:
        raise PermissionDenied("An active persisted account is required.")
    return persisted


def _require_lister_actor(actor):
    actor = _active_persisted_actor(actor)
    if not can_create_property_record(actor):
        raise PermissionDenied("An active Owner or Agent role is required.")
    return actor


def _ensure_can_view(actor, property_record):
    if can_view_property_record(actor, property_record):
        return
    raise PermissionDenied("You do not have access to this property record.")


def _ensure_can_update(actor, property_record):
    if can_update_property_record(actor, property_record):
        return
    raise PermissionDenied("You do not have access to this property record.")


def _clean_service_attrs(attrs):
    protected = PROPERTY_RECORD_SERVER_FIELDS.intersection(attrs)
    if protected:
        raise ValidationError({field: "This field is server-controlled." for field in sorted(protected)})

    unsupported = set(attrs) - PROPERTY_RECORD_MUTABLE_FIELDS - PROPERTY_LOCALITY_INPUT_FIELDS
    if unsupported:
        raise ValidationError({field: "This field is not supported for property records." for field in sorted(unsupported)})

    return {field: attrs[field] for field in PROPERTY_RECORD_MUTABLE_FIELDS | PROPERTY_LOCALITY_INPUT_FIELDS if field in attrs}


def _validate_property_record(property_record):
    try:
        property_record.full_clean()
    except DjangoValidationError as exc:
        raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc


def _property_audit_state(property_record):
    return {
        "property_id": property_record.property_id,
        "category": property_record.category,
        "locality_id": str(property_record.locality_id),
        "locality_approved": bool(property_record.locality.approved),
        "size_unit": property_record.size_unit,
    }


def _audit_property_created(*, actor, property_record, request=None):
    create_audit_log(
        actor=actor,
        action=PROPERTY_CREATED,
        entity_type="PropertyRecord",
        entity_id=property_record.pk,
        before={},
        after=_property_audit_state(property_record),
        request=request,
    )


def _audit_property_updated(*, actor, property_record, changed_fields, request=None):
    create_audit_log(
        actor=actor,
        action=PROPERTY_UPDATED,
        entity_type="PropertyRecord",
        entity_id=property_record.pk,
        before={},
        after={
            "property_id": property_record.property_id,
            "changed_fields": sorted(changed_fields),
        },
        request=request,
    )


def _field_value(property_record, field):
    if field in {"region", "district", "ward", "locality"}:
        return getattr(property_record, f"{field}_id")
    return getattr(property_record, field)


def _geometry_changed(before, after):
    if before is None or after is None:
        return before is not after
    return not before.equals_exact(after, tolerance=0)


def _values_differ(before, after):
    if hasattr(before, "equals_exact") or hasattr(after, "equals_exact"):
        return _geometry_changed(before, after)
    return before != after


def _effective_changed_fields(property_record, values):
    changed = set()
    for field, value in values.items():
        before = _field_value(property_record, field)
        after = getattr(value, "pk", value) if field in {"region", "district", "ward", "locality"} else value
        if _values_differ(before, after):
            changed.add(field)
    return changed


def _validate_hierarchy(*, region, district, ward, locality=None):
    errors = {}
    if region is None:
        errors["region"] = "Region is required."
    if district is None:
        errors["district"] = "District is required."
    if ward is None:
        errors["ward"] = "Ward is required."

    if not errors:
        if district.region_id != region.pk:
            errors["district"] = "District must belong to the selected region."
        if ward.district_id != district.pk:
            errors["ward"] = "Ward must belong to the selected district."
        if locality is not None and locality.ward_id != ward.pk:
            errors["locality"] = "Locality must belong to the selected ward."

    if errors:
        raise ValidationError(errors)


def resolve_property_locality(*, actor, region, district, ward, locality=None, locality_name=None, locality_kind=None):
    has_existing = locality is not None
    has_name = locality_name is not None
    has_kind = locality_kind is not None

    if has_existing and (has_name or has_kind):
        raise ValidationError({"locality": "Use either an existing locality or typed locality input, not both."})
    if has_name != has_kind:
        raise ValidationError({"locality": "Both locality_name and locality_kind are required for typed locality input."})
    if not has_existing and not has_name:
        raise ValidationError({"locality": "A locality or typed locality input is required."})

    if has_existing:
        _validate_hierarchy(region=region, district=district, ward=ward, locality=locality)
        return locality

    if locality_kind not in {choice.value for choice in Locality.Kind}:
        raise ValidationError({"locality_kind": "A valid locality kind is required."})
    _validate_hierarchy(region=region, district=district, ward=ward)
    try:
        return create_pending_locality(actor=actor, ward=ward, name=locality_name, kind=locality_kind)
    except DjangoValidationError as exc:
        raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc


@transaction.atomic
def create_property_record(*, actor, request=None, **attrs):
    actor = _require_lister_actor(actor)
    values = _clean_service_attrs(attrs)
    values["locality"] = resolve_property_locality(
        actor=actor,
        region=values.get("region"),
        district=values.get("district"),
        ward=values.get("ward"),
        locality=values.pop("locality", None),
        locality_name=values.pop("locality_name", None),
        locality_kind=values.pop("locality_kind", None),
    )

    for _ in range(PROPERTY_ID_MAX_ATTEMPTS):
        property_record = PropertyRecord(property_id=generate_property_id(), created_by=actor, **values)
        _validate_property_record(property_record)
        try:
            with transaction.atomic():
                property_record.save()
                _audit_property_created(actor=actor, property_record=property_record, request=request)
            return property_record
        except IntegrityError as exc:
            if "property_id" not in str(exc).lower():
                raise

    raise ValidationError({"property_id": "Could not create a unique property identifier."})


def get_property_record(*, actor, property_id):
    actor = _active_persisted_actor(actor)
    try:
        property_record = PropertyRecord.objects.select_related(
            "created_by",
            "region",
            "district",
            "ward",
            "locality",
        ).get(property_id=property_id)
    except PropertyRecord.DoesNotExist as exc:
        raise NotFound("Property record was not found.") from exc

    _ensure_can_view(actor, property_record)
    return property_record


@transaction.atomic
def update_property_record(*, actor, property_record, request=None, **attrs):
    actor = _active_persisted_actor(actor)
    values = _clean_service_attrs(attrs)

    record_id = getattr(property_record, "pk", property_record)
    try:
        locked = PropertyRecord.objects.select_for_update().get(pk=record_id)
    except (TypeError, ValueError, PropertyRecord.DoesNotExist) as exc:
        raise NotFound("Property record was not found.") from exc

    _ensure_can_update(actor, locked)
    locality = values.pop("locality", None)
    locality_name = values.pop("locality_name", None)
    locality_kind = values.pop("locality_kind", None)
    if locality is not None or locality_name is not None or locality_kind is not None:
        values["locality"] = resolve_property_locality(
            actor=actor,
            region=values.get("region", locked.region),
            district=values.get("district", locked.district),
            ward=values.get("ward", locked.ward),
            locality=locality,
            locality_name=locality_name,
            locality_kind=locality_kind,
        )
    changed_fields = _effective_changed_fields(locked, values)
    for field, value in values.items():
        setattr(locked, field, value)
    _validate_property_record(locked)
    if changed_fields:
        locked.save(update_fields=[*values.keys(), "updated_at"])
        _audit_property_updated(actor=actor, property_record=locked, changed_fields=changed_fields, request=request)
    return locked
