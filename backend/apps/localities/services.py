from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.services import create_audit_log
from apps.roles.catalog import ROLE_MANAGEMENT
from apps.roles.services import user_has_role

from .audit_events import LOCALITY_APPROVED, LOCALITY_CREATED
from .models import District, Locality, Region, Ward


SUMMARY_KEYS = (
    "regions_created",
    "districts_created",
    "wards_created",
    "regions_existing",
    "districts_existing",
    "wards_existing",
)


def _empty_summary():
    return {key: 0 for key in SUMMARY_KEYS}


def _normalize_name(value):
    return (value or "").strip()


def _require_mapping(value, path):
    if not isinstance(value, dict):
        raise DjangoValidationError(f"{path} must be an object.")


def _require_collection(value, path):
    if not isinstance(value, list):
        raise DjangoValidationError(f"{path} must be a list.")


def _validated_name(value, path):
    if value is None:
        raise DjangoValidationError(f"{path} is required.")
    if not isinstance(value, str):
        raise DjangoValidationError(f"{path} must be a string.")
    normalized = _normalize_name(value)
    if not normalized:
        raise DjangoValidationError(f"{path} cannot be blank.")
    return normalized


def _validate_reference_data(data):
    _require_collection(data, "localities")
    validated = []

    for region_index, region_data in enumerate(data):
        region_path = f"localities[{region_index}]"
        _require_mapping(region_data, region_path)
        region_name = _validated_name(region_data.get("name"), f"{region_path}.name")

        if "districts" not in region_data:
            raise DjangoValidationError(f"{region_path}.districts is required.")
        districts_data = region_data["districts"]
        _require_collection(districts_data, f"{region_path}.districts")

        districts = []
        for district_index, district_data in enumerate(districts_data):
            district_path = f"{region_path}.districts[{district_index}]"
            _require_mapping(district_data, district_path)
            district_name = _validated_name(district_data.get("name"), f"{district_path}.name")

            if "wards" not in district_data:
                raise DjangoValidationError(f"{district_path}.wards is required.")
            wards_data = district_data["wards"]
            _require_collection(wards_data, f"{district_path}.wards")

            wards = []
            for ward_index, ward_data in enumerate(wards_data):
                ward_path = f"{district_path}.wards[{ward_index}]"
                _require_mapping(ward_data, ward_path)
                wards.append({"name": _validated_name(ward_data.get("name"), f"{ward_path}.name")})

            districts.append({"name": district_name, "wards": wards})

        validated.append({"name": region_name, "districts": districts})

    return validated


def _get_or_create_case_insensitive(model, *, lookup, create):
    existing = model.objects.filter(**lookup).first()
    if existing is not None:
        return existing, False

    try:
        with transaction.atomic():
            return model.objects.create(**create), True
    except IntegrityError:
        return model.objects.get(**lookup), False


def import_reference_localities(data):
    """Additively import controlled Region/District/Ward reference data."""
    validated = _validate_reference_data(data)
    summary = _empty_summary()

    with transaction.atomic():
        for region_data in validated:
            region, created = _get_or_create_case_insensitive(
                Region,
                lookup={"name__iexact": region_data["name"]},
                create={"name": region_data["name"]},
            )
            summary["regions_created" if created else "regions_existing"] += 1

            for district_data in region_data["districts"]:
                district, created = _get_or_create_case_insensitive(
                    District,
                    lookup={"region": region, "name__iexact": district_data["name"]},
                    create={"region": region, "name": district_data["name"]},
                )
                summary["districts_created" if created else "districts_existing"] += 1

                for ward_data in district_data["wards"]:
                    _, created = _get_or_create_case_insensitive(
                        Ward,
                        lookup={"district": district, "name__iexact": ward_data["name"]},
                        create={"district": district, "name": ward_data["name"]},
                    )
                    summary["wards_created" if created else "wards_existing"] += 1

    return summary


def _require_persisted_actor(actor):
    if actor is None or not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("An authenticated actor is required.")
    if not getattr(actor, "pk", None):
        raise PermissionDenied("A persisted actor is required.")
    if not actor.__class__._default_manager.filter(pk=actor.pk, is_active=True).exists():
        raise PermissionDenied("A persisted active actor is required.")
    return actor


def _require_management(actor):
    actor = _require_persisted_actor(actor)
    if not user_has_role(actor, ROLE_MANAGEMENT):
        raise PermissionDenied("Active Management role is required.")
    return actor


def _resolve_ward(ward):
    ward_id = getattr(ward, "pk", ward)
    if not ward_id:
        raise ValidationError({"ward": "A persisted ward is required."})
    try:
        return Ward.objects.select_for_update().get(pk=ward_id)
    except (TypeError, ValueError, Ward.DoesNotExist) as exc:
        raise ValidationError({"ward": "A valid ward is required."}) from exc


def _validated_locality_name(name):
    normalized = _normalize_name(name)
    if not normalized:
        raise ValidationError({"name": "Name is required."})
    return normalized


def _validated_locality_kind(kind):
    valid_kinds = {choice.value for choice in Locality.Kind}
    if kind not in valid_kinds:
        raise ValidationError({"kind": "A valid locality kind is required."})
    return kind


def _create_locality(*, actor, ward, name, kind, approved, reject_duplicate):
    actor = _require_persisted_actor(actor)
    name = _validated_locality_name(name)
    kind = _validated_locality_kind(kind)

    with transaction.atomic():
        ward = _resolve_ward(ward)
        existing = Locality.objects.select_for_update().filter(
            ward=ward,
            kind=kind,
            name__iexact=name,
        ).first()
        if existing is not None:
            if reject_duplicate:
                raise ValidationError({"name": "A locality with this ward, kind, and name already exists."})
            return existing

        try:
            return Locality.objects.create(
                ward=ward,
                name=name,
                kind=kind,
                approved=approved,
                created_by=actor,
            )
        except IntegrityError as exc:
            if reject_duplicate:
                raise ValidationError({"name": "A locality with this ward, kind, and name already exists."}) from exc
            return Locality.objects.get(ward=ward, kind=kind, name__iexact=name)


def _locality_audit_state(locality):
    return {
        "locality_id": str(locality.pk),
        "name": locality.name,
        "kind": locality.kind,
        "ward_id": str(locality.ward_id),
        "approved": locality.approved,
    }


def create_locality(*, actor, ward, name, kind, request=None):
    """Create a trusted, management-approved Street/Village locality."""
    actor = _require_management(actor)
    with transaction.atomic():
        locality = _create_locality(actor=actor, ward=ward, name=name, kind=kind, approved=True, reject_duplicate=True)
        create_audit_log(
            actor=actor,
            action=LOCALITY_CREATED,
            entity_type="Locality",
            entity_id=locality.pk,
            before={},
            after=_locality_audit_state(locality),
            request=request,
        )
        return locality


def create_pending_locality(*, actor, ward, name, kind):
    """Create or return a pending locality record for future listing flows."""
    return _create_locality(actor=actor, ward=ward, name=name, kind=kind, approved=False, reject_duplicate=False)


def approve_locality(*, locality, approved_by, request=None):
    actor = _require_management(approved_by)
    locality_id = getattr(locality, "pk", locality)
    if not locality_id:
        raise ValidationError({"locality": "A persisted locality is required."})

    with transaction.atomic():
        try:
            locality = Locality.objects.select_for_update().get(pk=locality_id)
        except (TypeError, ValueError, Locality.DoesNotExist) as exc:
            raise ValidationError({"locality": "A valid locality is required."}) from exc

        if locality.approved:
            return locality
        before = _locality_audit_state(locality)
        locality.approved = True
        locality.save(update_fields=["approved", "updated_at"])
        create_audit_log(
            actor=actor,
            action=LOCALITY_APPROVED,
            entity_type="Locality",
            entity_id=locality.pk,
            before=before,
            after=_locality_audit_state(locality),
            request=request,
        )
        return locality
