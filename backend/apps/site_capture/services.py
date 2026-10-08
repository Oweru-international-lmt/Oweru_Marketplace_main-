import secrets
from collections.abc import Mapping

from django.contrib.gis.geos import Point, Polygon
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.audit.services import create_audit_log
from apps.properties.models import PropertyRecord
from apps.properties.policies import can_update_property_record, can_view_property_record, get_active_persisted_actor
from apps.properties.serializers import GeoJSONPointField, GeoJSONPolygonField
from apps.properties.services import update_property_record

from .audit_events import SITE_CAPTURE_CREATED, SITE_CAPTURE_PROMOTED, SITE_CAPTURE_SUBMITTED, SITE_CAPTURE_UPDATED
from .models import SiteCapture
from .models import CaptureCorner
from decimal import Decimal, InvalidOperation
from django.db import connection
from apps.verification.configuration import setting


CAPTURE_ID_PREFIX = "CAP"
CAPTURE_ID_TOKEN_BYTES = 8
CAPTURE_ID_MAX_ATTEMPTS = 8

SITE_CAPTURE_MUTABLE_FIELDS = frozenset({"observed_point", "observed_boundary"})
SITE_CAPTURE_SERVER_FIELDS = frozenset({
    "id",
    "capture_id",
    "property",
    "captured_by",
    "captured_at",
    "status",
    "created_at",
    "updated_at",
})


def _capture_id_token():
    return secrets.token_hex(CAPTURE_ID_TOKEN_BYTES).upper()


def generate_capture_id():
    for _ in range(CAPTURE_ID_MAX_ATTEMPTS):
        candidate = f"{CAPTURE_ID_PREFIX}-{_capture_id_token()}"
        if not SiteCapture.objects.filter(capture_id=candidate).exists():
            return candidate
    raise ValidationError({"capture_id": "Could not generate a unique site-capture identifier."})


def _active_persisted_actor(actor):
    persisted = get_active_persisted_actor(actor)
    if persisted is None:
        raise PermissionDenied("An active persisted account is required.")
    return persisted


def _ensure_can_update_property(actor, property_record):
    if not can_update_property_record(actor, property_record):
        raise PermissionDenied("You do not have access to this property record.")


def _ensure_can_capture(actor, property_record):
    if can_update_property_record(actor, property_record):
        return
    from apps.verification.models import VerificationTask
    owner_task = VerificationTask.objects.filter(job__property=property_record, job__status="IN_PROGRESS", job__invalidated_at__isnull=True, job__owner_user=actor, job__listing__isnull=True, kind="SITE_CAPTURE", status="ASSIGNED", assignee=actor, job__payment_receipt__isnull=False, job__consent__decision="CONFIRM").first()
    if owner_task and actor.has_role("owner"):
        return
    from apps.verification.conflicts import has_property_conflict
    task = VerificationTask.objects.filter(
        job__property=property_record, job__status="IN_PROGRESS", assignee=actor,
        kind="PROFESSIONAL", professional_type="SURVEYOR", status="ACCEPTED",
        due_at__gt=timezone.now(),
    ).first()
    if task and not has_property_conflict(actor, property_record):
        from apps.professionals.services import eligible_professionals
        if any(profile.user_id == actor.pk for profile in eligible_professionals(property_record=property_record, professional_type="SURVEYOR")):
            return
    raise PermissionDenied("Only the lister or assigned surveyor may capture this property.")


def _ensure_can_view_property(actor, property_record):
    if not can_view_property_record(actor, property_record):
        raise PermissionDenied("You do not have access to this property record.")


def _resolve_property_record(property_record, *, lock=False):
    property_id = getattr(property_record, "pk", property_record)
    if not property_id:
        raise ValidationError({"property_record": "A persisted property record is required."})

    queryset = PropertyRecord.objects
    if lock:
        queryset = queryset.select_for_update()
    try:
        return queryset.get(pk=property_id)
    except (TypeError, ValueError, DjangoValidationError, PropertyRecord.DoesNotExist) as exc:
        raise ValidationError({"property_record": "A valid property record is required."}) from exc


def _resolve_locked_capture(site_capture):
    capture_id = getattr(site_capture, "pk", site_capture)
    if not capture_id:
        raise NotFound("Site capture was not found.")
    try:
        return SiteCapture.objects.select_for_update().select_related("property", "captured_by").get(pk=capture_id)
    except (TypeError, ValueError, DjangoValidationError, SiteCapture.DoesNotExist) as exc:
        raise NotFound("Site capture was not found.") from exc


def get_site_capture(*, capture_id, actor):
    actor = _active_persisted_actor(actor)
    try:
        site_capture = SiteCapture.objects.select_related("property").get(capture_id=capture_id)
    except SiteCapture.DoesNotExist as exc:
        raise NotFound("Site capture was not found.") from exc
    _ensure_can_read_capture(actor, site_capture)
    return site_capture


def _ensure_can_read_capture(actor, capture):
    from apps.verification.access import visible_tasks
    if capture.verification_task_id:
        from apps.leads.policies import management
        if management(actor) and actor.has_marketplace_permission("verification.record_result"):
            return
        if visible_tasks(actor).filter(job_id=capture.verification_task.job_id).exists():
            return
        raise PermissionDenied("This capture belongs to another private Full Check.")
    if can_view_property_record(actor, capture.property):
        return
    if visible_tasks(actor).filter(job__tasks__submissions__capture=capture).exists():
        return
    _ensure_can_capture(actor, capture.property)


def _ensure_can_edit_capture(actor, capture):
    if capture.verification_task_id:
        if capture.captured_by_id != actor.pk:
            raise PermissionDenied("Only the assigned capturing person may change this private draft.")
        from apps.verification.task_services import require_work, require_task_actor
        task = capture.verification_task
        require_work(task.job)
        require_task_actor(actor, task.job, task)
        if task.status not in {"ASSIGNED", "ACCEPTED"}:
            raise ValidationError("This capture task is no longer open.")
    _ensure_can_capture(actor, capture.property)


def capture_task(*, actor, property_record, task_id=None):
    from django.db.models import Q
    from apps.verification.models import VerificationTask
    from apps.verification.task_services import require_task_actor
    tasks = VerificationTask.objects.select_for_update(of=("self",)).select_related("job__property", "job__listing").filter(job__property=property_record, job__status="IN_PROGRESS", job__invalidated_at__isnull=True, job__payment_receipt__isnull=False, job__consent__decision="CONFIRM", assignee=actor).filter(Q(kind="SITE_CAPTURE", status="ASSIGNED") | Q(kind="PROFESSIONAL", professional_type="SURVEYOR", status="ACCEPTED", due_at__gt=timezone.now())).order_by("pk")
    if task_id:
        task = tasks.filter(pk=task_id).first()
        if task is None:
            raise PermissionDenied("This capture task is outside your live assignment.")
    else:
        matches = list(tasks[:2])
        if len(matches) > 1:
            raise ValidationError("Select verification_task_id when more than one Full Check capture task is assigned.")
        task = matches[0] if matches else None
    if task:
        require_task_actor(actor, task.job, task)
    return task


def get_property_site_captures(*, property_record, actor):
    actor = _active_persisted_actor(actor)
    if not can_view_property_record(actor, property_record):
        from apps.verification.access import visible_tasks
        if not visible_tasks(actor).filter(job__property=property_record).exists():
            _ensure_can_capture(actor, property_record)
    readable_ids = []
    for capture in SiteCapture.objects.filter(property=property_record).select_related("property", "verification_task__job"):
        try:
            _ensure_can_read_capture(actor, capture)
            readable_ids.append(capture.pk)
        except PermissionDenied:
            continue
    return (
        SiteCapture.objects.filter(property=property_record, pk__in=readable_ids)
        .select_related("property")
        .order_by("-captured_at", "-created_at", "-id")
    )


def _clean_update_attrs(attrs):
    protected = SITE_CAPTURE_SERVER_FIELDS.intersection(attrs)
    if protected:
        raise ValidationError({field: "This field is server-controlled." for field in sorted(protected)})

    unsupported = set(attrs) - SITE_CAPTURE_MUTABLE_FIELDS
    if unsupported:
        raise ValidationError({field: "This field is not supported for site captures." for field in sorted(unsupported)})

    return {field: attrs[field] for field in SITE_CAPTURE_MUTABLE_FIELDS if field in attrs}


def _validate_site_capture(site_capture):
    try:
        site_capture.full_clean()
    except DjangoValidationError as exc:
        raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc


def _invalid_geometry(field, message):
    raise ValidationError({field: message})


def _normalize_observed_point(value):
    if isinstance(value, Point):
        if value.empty:
            _invalid_geometry("observed_point", "Observed point must not be empty.")
        if value.srid != 4326:
            _invalid_geometry("observed_point", "Observed point must use SRID 4326.")
        value = {"type": "Point", "coordinates": [value.x, value.y]}
    elif not isinstance(value, Mapping):
        _invalid_geometry("observed_point", "Observed point must be a GeoJSON Point or SRID 4326 GEOS Point.")

    try:
        return GeoJSONPointField().run_validation(value)
    except ValidationError as exc:
        raise ValidationError({"observed_point": exc.detail}) from exc


def _normalize_observed_boundary(value):
    if value is None:
        return None
    if isinstance(value, Polygon):
        if value.empty:
            _invalid_geometry("observed_boundary", "Observed boundary must not be empty.")
        if value.srid != 4326:
            _invalid_geometry("observed_boundary", "Observed boundary must use SRID 4326.")
        value = {
            "type": "Polygon",
            "coordinates": [[list(pair) for pair in ring] for ring in value.coords],
        }
    elif not isinstance(value, Mapping):
        _invalid_geometry(
            "observed_boundary",
            "Observed boundary must be a GeoJSON Polygon or SRID 4326 GEOS Polygon.",
        )

    try:
        return GeoJSONPolygonField().run_validation(value)
    except ValidationError as exc:
        raise ValidationError({"observed_boundary": exc.detail}) from exc


def _normalize_gis_values(values):
    normalized = dict(values)
    if "observed_point" in normalized:
        normalized["observed_point"] = _normalize_observed_point(normalized["observed_point"])
    if "observed_boundary" in normalized:
        normalized["observed_boundary"] = _normalize_observed_boundary(normalized["observed_boundary"])
    return normalized


def _capture_audit_state(site_capture):
    return {
        "capture_id": site_capture.capture_id,
        "property_id": str(site_capture.property_id),
        "status": site_capture.status,
    }


def _audit_capture_created(*, actor, site_capture, request=None):
    create_audit_log(
        actor=actor,
        action=SITE_CAPTURE_CREATED,
        entity_type="SiteCapture",
        entity_id=site_capture.pk,
        before={},
        after=_capture_audit_state(site_capture),
        request=request,
    )


def _audit_capture_updated(*, actor, site_capture, changed_fields, request=None):
    create_audit_log(
        actor=actor,
        action=SITE_CAPTURE_UPDATED,
        entity_type="SiteCapture",
        entity_id=site_capture.pk,
        before={},
        after={
            "capture_id": site_capture.capture_id,
            "property_id": str(site_capture.property_id),
            "changed_fields": sorted(changed_fields),
        },
        request=request,
    )


def _audit_capture_submitted(*, actor, site_capture, from_status, request=None):
    create_audit_log(
        actor=actor,
        action=SITE_CAPTURE_SUBMITTED,
        entity_type="SiteCapture",
        entity_id=site_capture.pk,
        before={},
        after={
            "capture_id": site_capture.capture_id,
            "property_id": str(site_capture.property_id),
            "from_status": from_status,
            "to_status": site_capture.status,
        },
        request=request,
    )


def _audit_capture_promoted(*, actor, site_capture, promoted_fields, request=None):
    create_audit_log(
        actor=actor,
        action=SITE_CAPTURE_PROMOTED,
        entity_type="SiteCapture",
        entity_id=site_capture.pk,
        before={},
        after={
            "capture_id": site_capture.capture_id,
            "property_id": str(site_capture.property_id),
            "promoted_fields": sorted(promoted_fields),
        },
        request=request,
    )


def _effective_changed_fields(site_capture, values):
    return {
        field
        for field, value in values.items()
        if not _geometries_equal(getattr(site_capture, field), value)
    }


def _geometries_equal(current, proposed):
    if current is None or proposed is None:
        return current is proposed
    return current.equals(proposed)


def _property_geometries_differ(before, after):
    if before is None or after is None:
        return before is not after
    return not before.equals_exact(after, tolerance=0)


def _promoted_property_fields(before, after, selected_fields):
    return {
        field
        for field in selected_fields
        if _property_geometries_differ(getattr(before, field), getattr(after, field))
    }


def _validate_promotion_selection(*, promote_point, promote_boundary, extra_selection):
    if extra_selection:
        raise ValidationError({field: "This field is not supported for site-capture promotion." for field in sorted(extra_selection)})
    if type(promote_point) is not bool or type(promote_boundary) is not bool:
        raise ValidationError("Promotion field selections must be boolean values.")
    if not promote_point and not promote_boundary:
        raise ValidationError("Select at least one observation to promote.")


@transaction.atomic
def create_site_capture(*, property_record, actor, observed_point, observed_boundary=None, verification_task_id=None, request=None):
    actor = _active_persisted_actor(actor)
    property_record = _resolve_property_record(property_record, lock=True)
    _ensure_can_capture(actor, property_record)
    task = capture_task(actor=actor, property_record=property_record, task_id=verification_task_id)
    observed_point = _normalize_observed_point(observed_point)
    observed_boundary = _normalize_observed_boundary(observed_boundary)

    for _ in range(CAPTURE_ID_MAX_ATTEMPTS):
        site_capture = SiteCapture(
            capture_id=generate_capture_id(),
            property=property_record,
            verification_task=task,
            captured_by=actor,
            captured_at=timezone.now(),
            observed_point=observed_point,
            observed_boundary=observed_boundary,
            status=SiteCapture.Status.DRAFT,
        )
        _validate_site_capture(site_capture)
        try:
            with transaction.atomic():
                site_capture.save()
                _audit_capture_created(actor=actor, site_capture=site_capture, request=request)
            return site_capture
        except IntegrityError as exc:
            if "capture_id" not in str(exc).lower():
                raise

    raise ValidationError({"capture_id": "Could not create a unique site-capture identifier."})


@transaction.atomic
def update_site_capture(*, site_capture, actor, request=None, **validated_changes):
    actor = _active_persisted_actor(actor)
    values = _normalize_gis_values(_clean_update_attrs(validated_changes))
    locked = _resolve_locked_capture(site_capture)
    _ensure_can_edit_capture(actor, locked)
    if locked.status != SiteCapture.Status.DRAFT:
        raise ValidationError({"status": "Submitted site captures cannot be changed."})

    changed_fields = _effective_changed_fields(locked, values)
    for field, value in values.items():
        setattr(locked, field, value)
    _validate_site_capture(locked)
    if changed_fields:
        locked.save(update_fields=[*values.keys(), "updated_at"])
        _audit_capture_updated(
            actor=actor,
            site_capture=locked,
            changed_fields=changed_fields,
            request=request,
        )
    return locked


@transaction.atomic
def submit_site_capture(*, site_capture, actor, request=None):
    actor = _active_persisted_actor(actor)
    locked = _resolve_locked_capture(site_capture)
    _ensure_can_edit_capture(actor, locked)
    if locked.status != SiteCapture.Status.DRAFT:
        raise ValidationError({"status": "Only draft site captures can be submitted."})

    corners = list(locked.corners.order_by("sequence"))
    if corners:
        if len(corners) < 3:
            raise ValidationError("At least three recorded corners are required.")
        coordinates = [(corner.point.x, corner.point.y) for corner in corners]
        locked.observed_boundary = _normalize_observed_boundary(Polygon([*coordinates, coordinates[0]], srid=4326))
    if locked.observed_boundary is None:
        raise ValidationError({"observed_boundary": "A valid boundary with at least three corners is required."})
    with connection.cursor() as cursor:
        cursor.execute("SELECT ST_Area(ST_GeomFromEWKT(%s)::geography)", [locked.observed_boundary.ewkt])
        area = Decimal(str(cursor.fetchone()[0])).quantize(Decimal("0.01"))
    if area <= 0:
        raise ValidationError("Boundary measured area must be positive.")
    locked.measured_area_sqm = area
    units = {"sqm": Decimal(1), "m2": Decimal(1), "acre": Decimal("4046.8564224"), "acres": Decimal("4046.8564224"), "hectare": Decimal(10000), "hectares": Decimal(10000), "ha": Decimal(10000)}
    multiplier = units.get(locked.property.size_unit.lower())
    flags = []
    if multiplier:
        stated = locked.property.stated_size * multiplier
        locked.area_difference_percent = (abs(area - stated) / stated * 100).quantize(Decimal("0.01"))
        if locked.area_difference_percent > Decimal(str(setting("area_difference_percent"))):
            flags.append("AREA_DIFFERENCE")
    else:
        flags.append("AREA_COMPARISON_UNAVAILABLE")
    import json
    from .models import PublicMapLayer
    overlaps = [{"kind": "PROPERTY_BOUNDARY", "reference": row.property_id, "geometry": json.loads(row.boundary.geojson)} for row in PropertyRecord.objects.exclude(pk=locked.property_id).filter(boundary__intersects=locked.observed_boundary)]
    overlaps += [{"kind": "PUBLIC_LAYER", "reference": str(row.pk), "name": row.name, "source_reference": row.source_reference, "geometry": json.loads(row.boundary.geojson)} for row in PublicMapLayer.objects.filter(active=True, boundary__intersects=locked.observed_boundary)]
    locked.overlap_findings = overlaps
    if overlaps:
        flags.append("BOUNDARY_INTERSECTION_REVIEW")
    for asset in locked.assets.all():
        flags.extend(flag for flag in asset.flags if flag not in flags)
    flags.append("SATELLITE_CHECK_UNAVAILABLE")
    locked.review_flags = flags

    previous_status = locked.status
    locked.status = SiteCapture.Status.SUBMITTED
    _validate_site_capture(locked)
    locked.save(update_fields=["status", "observed_boundary", "measured_area_sqm", "area_difference_percent", "review_flags", "overlap_findings", "updated_at"])
    _audit_capture_submitted(
        actor=actor,
        site_capture=locked,
        from_status=previous_status,
        request=request,
    )
    return locked


@transaction.atomic
def record_corner(*, actor, site_capture, point, accuracy_m, observed_at, device, request=None):
    actor = _active_persisted_actor(actor)
    locked = _resolve_locked_capture(site_capture)
    _ensure_can_edit_capture(actor, locked)
    if locked.status != "DRAFT":
        raise ValidationError("Submitted capture is locked.")
    point = _normalize_observed_point(point)
    try:
        accuracy = Decimal(str(accuracy_m))
    except InvalidOperation as exc:
        raise ValidationError("Accuracy must be a finite number.") from exc
    if isinstance(accuracy_m, bool) or not accuracy.is_finite() or accuracy < 0 or accuracy > Decimal(str(setting("corner_accuracy_m"))):
        raise ValidationError("Corner accuracy is outside the configured limit; wait and retry.")
    if not observed_at or not timezone.is_aware(observed_at) or not isinstance(device, str) or not device.strip() or len(device) > 255:
        raise ValidationError("An aware capture timestamp and device are required.")
    corner = CaptureCorner.objects.create(capture=locked, sequence=locked.corners.count() + 1, point=point, accuracy_m=accuracy, observed_at=observed_at, device=device.strip())
    create_audit_log(actor=actor, action="site_capture.corner_recorded", entity_type="SiteCapture", entity_id=locked.pk, before={}, after={"sequence": corner.sequence}, request=request)
    return corner


def require_full_check_capture(capture, property_record):
    if capture.property_id != property_record.pk or capture.status != "SUBMITTED" or capture.observed_boundary is None or capture.measured_area_sqm is None or capture.measured_area_sqm <= 0 or capture.corners.count() < 3:
        raise ValidationError("Full Check requires a submitted measured boundary with at least three recorded corners.")
    return capture


@transaction.atomic
def promote_site_capture(
    *,
    site_capture,
    actor,
    promote_point=True,
    promote_boundary=False,
    request=None,
    **extra_selection,
):
    _validate_promotion_selection(
        promote_point=promote_point,
        promote_boundary=promote_boundary,
        extra_selection=extra_selection,
    )
    actor = _active_persisted_actor(actor)
    locked = _resolve_locked_capture(site_capture)
    _ensure_can_update_property(actor, locked.property)
    _ensure_can_read_capture(actor, locked)
    if locked.status != SiteCapture.Status.SUBMITTED:
        raise ValidationError({"status": "Only submitted site captures can be promoted."})
    if promote_boundary and locked.observed_boundary is None:
        raise ValidationError({"observed_boundary": "This site capture has no observed boundary to promote."})

    values = {}
    if promote_point:
        values["pin"] = locked.observed_point
    if promote_boundary:
        values["boundary"] = locked.observed_boundary

    property_before = locked.property
    updated_property = update_property_record(
        actor=actor,
        property_record=locked.property,
        request=request,
        **values,
    )
    promoted_fields = _promoted_property_fields(property_before, updated_property, values)
    if promoted_fields:
        _audit_capture_promoted(
            actor=actor,
            site_capture=locked,
            promoted_fields=promoted_fields,
            request=request,
        )
    return updated_property


def upload_site_capture_image(*, site_capture, actor, image, captured_at=None, captured_location=None, device="", request=None):
    from apps.media.services import upload_site_capture_image as upload_media

    return upload_media(
        site_capture=site_capture,
        actor=actor,
        image=image,
        captured_at=captured_at,
        captured_location=captured_location,
        device=device,
        request=request,
    )


def remove_site_capture_media(*, site_capture, media, actor, request=None):
    from apps.media.services import remove_site_capture_media as remove_media

    return remove_media(site_capture=site_capture, media=media, actor=actor, request=request)
