from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.audit.services import create_audit_log
from apps.localities.models import District, Region, Ward
from apps.properties.models import PropertyRecord
from apps.properties.policies import get_active_persisted_actor
from apps.roles.catalog import ROLE_LOCAL_OFFICIAL, ROLE_MANAGEMENT
from apps.roles.services import user_has_role

from .audit_events import (
    LOCAL_OFFICIAL_JURISDICTION_ASSIGNED,
    LOCAL_OFFICIAL_JURISDICTION_REVOKED,
    LOCAL_OFFICIAL_PROFILE_CREATED,
    LOCAL_OFFICIAL_PROFILE_DEACTIVATED,
    LOCAL_OFFICIAL_PROFILE_REACTIVATED,
    LOCAL_OFFICIAL_PROFILE_UPDATED,
)
from .models import LocalOfficialProfile, OfficialJurisdictionAssignment, generate_assignment_id, generate_official_id


PROFILE_MUTABLE_FIELDS = frozenset({"official_number", "is_active"})


def _now(at=None):
    return at or timezone.now()


def _active_management_actor(actor):
    persisted = get_active_persisted_actor(actor)
    if persisted is None or not user_has_role(persisted, ROLE_MANAGEMENT):
        raise PermissionDenied("An active Management role is required.")
    try:
        return User.objects.select_for_update().get(pk=persisted.pk, is_active=True)
    except User.DoesNotExist as exc:
        raise PermissionDenied("An active Management role is required.") from exc


def _active_local_official_user(user):
    user_id = getattr(user, "pk", user)
    try:
        target = User.objects.select_for_update().get(pk=user_id, is_active=True)
    except (TypeError, ValueError, User.DoesNotExist) as exc:
        raise ValidationError({"user": "An active persisted Local Official user is required."}) from exc
    if not user_has_role(target, ROLE_LOCAL_OFFICIAL):
        raise ValidationError({"user": "Target user must hold an active Local Official role."})
    return target


def _normalize_official_number(value):
    if not isinstance(value, str):
        raise ValidationError({"official_number": "Official number is required."})
    normalized = value.strip()
    if not normalized:
        raise ValidationError({"official_number": "Official number is required."})
    return normalized


def _profile_for_update(profile):
    profile_id = getattr(profile, "pk", profile)
    try:
        return LocalOfficialProfile.objects.select_for_update().select_related("user").get(pk=profile_id)
    except (TypeError, ValueError, LocalOfficialProfile.DoesNotExist) as exc:
        raise NotFound("Local Official profile was not found.") from exc


def _assignment_for_update(assignment):
    assignment_id = getattr(assignment, "pk", assignment)
    try:
        return OfficialJurisdictionAssignment.objects.select_for_update().select_related("official__user").get(pk=assignment_id)
    except (TypeError, ValueError, OfficialJurisdictionAssignment.DoesNotExist) as exc:
        raise NotFound("Official jurisdiction assignment was not found.") from exc


def _profile_audit_state(profile, *, changed_fields=None):
    state = {"official_id": profile.official_id, "is_active": profile.is_active}
    if changed_fields is not None:
        state["changed_fields"] = sorted(changed_fields)
    return state


def _assignment_area_id(assignment):
    if assignment.scope_type == OfficialJurisdictionAssignment.ScopeType.REGION:
        return str(assignment.region_id)
    if assignment.scope_type == OfficialJurisdictionAssignment.ScopeType.DISTRICT:
        return str(assignment.district_id)
    return str(assignment.ward_id)


def _assignment_audit_state(assignment):
    return {
        "official_id": assignment.official.official_id,
        "assignment_id": assignment.assignment_id,
        "scope_type": assignment.scope_type,
        "area_id": _assignment_area_id(assignment),
        "status": assignment.status,
    }


def _validate_model(instance):
    try:
        instance.full_clean()
    except DjangoValidationError as exc:
        raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc


@transaction.atomic
def create_local_official_profile(*, actor, user, official_number, request=None):
    actor = _active_management_actor(actor)
    target = _active_local_official_user(user)
    official_number = _normalize_official_number(official_number)
    if LocalOfficialProfile.objects.select_for_update().filter(user=target).exists():
        raise ValidationError({"user": "A Local Official profile already exists for this user."})

    for _ in range(8):
        profile = LocalOfficialProfile(
            official_id=generate_official_id(),
            user=target,
            official_number=official_number,
            is_active=True,
        )
        _validate_model(profile)
        try:
            with transaction.atomic():
                profile.save()
                create_audit_log(
                    actor=actor,
                    action=LOCAL_OFFICIAL_PROFILE_CREATED,
                    entity_type="LocalOfficialProfile",
                    entity_id=profile.pk,
                    before={},
                    after=_profile_audit_state(profile),
                    request=request,
                )
            return profile
        except IntegrityError as exc:
            if "official_id" not in str(exc).lower():
                raise ValidationError({"official_number": "Official number must be unique."}) from exc

    raise ValidationError({"official_id": "Could not create a unique Local Official profile."})


@transaction.atomic
def update_local_official_profile(*, actor, profile, request=None, **attrs):
    actor = _active_management_actor(actor)
    protected = set(attrs) - PROFILE_MUTABLE_FIELDS
    if protected:
        raise ValidationError({field: "This field is not supported." for field in sorted(protected)})
    locked = _profile_for_update(profile)
    values = dict(attrs)
    if "official_number" in values:
        values["official_number"] = _normalize_official_number(values["official_number"])

    changed_fields = {field for field, value in values.items() if getattr(locked, field) != value}
    if not changed_fields:
        return locked
    for field, value in values.items():
        setattr(locked, field, value)
    _validate_model(locked)
    try:
        locked.save(update_fields=[*values.keys(), "updated_at"])
    except IntegrityError as exc:
        raise ValidationError({"official_number": "Official number must be unique."}) from exc

    if "is_active" in changed_fields:
        action = LOCAL_OFFICIAL_PROFILE_REACTIVATED if locked.is_active else LOCAL_OFFICIAL_PROFILE_DEACTIVATED
    else:
        action = LOCAL_OFFICIAL_PROFILE_UPDATED
    create_audit_log(
        actor=actor,
        action=action,
        entity_type="LocalOfficialProfile",
        entity_id=locked.pk,
        before={},
        after=_profile_audit_state(locked, changed_fields=changed_fields),
        request=request,
    )
    return locked


def _resolve_scope(*, scope_type, region, district, ward):
    scopes = OfficialJurisdictionAssignment.ScopeType
    expected = {
        scopes.REGION: ("region", Region, region),
        scopes.DISTRICT: ("district", District, district),
        scopes.WARD: ("ward", Ward, ward),
    }
    if scope_type not in expected:
        raise ValidationError({"scope_type": "A valid jurisdiction scope is required."})
    field, model, value = expected[scope_type]
    if sum(item is not None for item in (region, district, ward)) != 1 or value is None:
        raise ValidationError({"scope_type": "Scope must match exactly one administrative area."})
    value_id = getattr(value, "pk", value)
    try:
        return field, model.objects.select_for_update().get(pk=value_id)
    except (TypeError, ValueError, model.DoesNotExist) as exc:
        raise ValidationError({field: "A valid canonical administrative area is required."}) from exc


def _validate_new_assignment_period(*, starts_at, expires_at):
    if starts_at is None:
        raise ValidationError({"starts_at": "Assignment start is required."})
    if expires_at is not None:
        if expires_at <= starts_at:
            raise ValidationError({"expires_at": "Expiry must be later than the assignment start."})
        if expires_at <= _now():
            raise ValidationError({"expires_at": "New assignments cannot already be expired."})


@transaction.atomic
def assign_jurisdiction(
    *,
    actor,
    official,
    scope_type,
    region=None,
    district=None,
    ward=None,
    starts_at,
    expires_at=None,
    request=None,
):
    actor = _active_management_actor(actor)
    profile = _profile_for_update(official)
    if not profile.is_active:
        raise ValidationError({"official": "Local Official profile is inactive."})
    _active_local_official_user(profile.user)
    field, area = _resolve_scope(scope_type=scope_type, region=region, district=district, ward=ward)
    _validate_new_assignment_period(starts_at=starts_at, expires_at=expires_at)

    values = {"region": None, "district": None, "ward": None}
    values[field] = area
    for _ in range(8):
        assignment = OfficialJurisdictionAssignment(
            assignment_id=generate_assignment_id(),
            official=profile,
            scope_type=scope_type,
            starts_at=starts_at,
            expires_at=expires_at,
            status=OfficialJurisdictionAssignment.Status.ACTIVE,
            assigned_by=actor,
            **values,
        )
        _validate_model(assignment)
        try:
            with transaction.atomic():
                assignment.save()
                create_audit_log(
                    actor=actor,
                    action=LOCAL_OFFICIAL_JURISDICTION_ASSIGNED,
                    entity_type="OfficialJurisdictionAssignment",
                    entity_id=assignment.pk,
                    before={},
                    after=_assignment_audit_state(assignment),
                    request=request,
                )
            return assignment
        except IntegrityError as exc:
            if "assignment_id" not in str(exc).lower():
                raise ValidationError({field: "An active assignment already exists for this scope."}) from exc

    raise ValidationError({"assignment_id": "Could not create a unique jurisdiction identifier."})


@transaction.atomic
def revoke_jurisdiction(*, actor, assignment, request=None):
    actor = _active_management_actor(actor)
    locked = _assignment_for_update(assignment)
    if locked.status != OfficialJurisdictionAssignment.Status.ACTIVE:
        raise ValidationError({"status": "Only active assignments can be revoked."})
    before = _assignment_audit_state(locked)
    locked.status = OfficialJurisdictionAssignment.Status.REVOKED
    locked.revoked_at = timezone.now()
    locked.revoked_by = actor
    _validate_model(locked)
    locked.save(update_fields=["status", "revoked_at", "revoked_by", "updated_at"])
    create_audit_log(
        actor=actor,
        action=LOCAL_OFFICIAL_JURISDICTION_REVOKED,
        entity_type="OfficialJurisdictionAssignment",
        entity_id=locked.pk,
        before=before,
        after=_assignment_audit_state(locked),
        request=request,
    )
    return locked


def is_effective_local_official(user, *, at=None):
    persisted = get_active_persisted_actor(user)
    return bool(
        persisted
        and user_has_role(persisted, ROLE_LOCAL_OFFICIAL)
        and LocalOfficialProfile.objects.filter(user=persisted, is_active=True).exists()
    )


def get_effective_jurisdiction_assignments(*, user, at=None):
    if not is_effective_local_official(user, at=at):
        return OfficialJurisdictionAssignment.objects.none()
    now = _now(at)
    return OfficialJurisdictionAssignment.objects.filter(
        official__user_id=user.pk,
        official__is_active=True,
        status=OfficialJurisdictionAssignment.Status.ACTIVE,
        starts_at__lte=now,
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))


def get_effective_jurisdiction_assignments_covering_property(*, user, property_record, at=None):
    """Return the user's effective assignments covering current property FKs."""
    if not isinstance(property_record, PropertyRecord):
        return OfficialJurisdictionAssignment.objects.none()
    return get_effective_jurisdiction_assignments(user=user, at=at).filter(
        Q(
            scope_type=OfficialJurisdictionAssignment.ScopeType.REGION,
            region_id=property_record.region_id,
        )
        | Q(
            scope_type=OfficialJurisdictionAssignment.ScopeType.DISTRICT,
            district_id=property_record.district_id,
        )
        | Q(
            scope_type=OfficialJurisdictionAssignment.ScopeType.WARD,
            ward_id=property_record.ward_id,
        )
    )


def filter_property_queryset_by_effective_jurisdiction(queryset, *, user, at=None):
    """Restrict PropertyRecord querysets to the user's effective jurisdiction."""
    assignments = get_effective_jurisdiction_assignments(user=user, at=at)
    return queryset.filter(
        Q(region_id__in=assignments.filter(
            scope_type=OfficialJurisdictionAssignment.ScopeType.REGION,
        ).values("region_id"))
        | Q(district_id__in=assignments.filter(
            scope_type=OfficialJurisdictionAssignment.ScopeType.DISTRICT,
        ).values("district_id"))
        | Q(ward_id__in=assignments.filter(
            scope_type=OfficialJurisdictionAssignment.ScopeType.WARD,
        ).values("ward_id"))
    )


def is_effective_jurisdiction_assignment(assignment, *, at=None):
    if not isinstance(assignment, OfficialJurisdictionAssignment):
        return False
    return get_effective_jurisdiction_assignments(
        user=assignment.official.user,
        at=at,
    ).filter(pk=assignment.pk).exists()


def assignment_covers_property(*, assignment, property_record):
    if not isinstance(assignment, OfficialJurisdictionAssignment) or not isinstance(property_record, PropertyRecord):
        return False
    if assignment.scope_type == OfficialJurisdictionAssignment.ScopeType.REGION:
        return assignment.region_id == property_record.region_id
    if assignment.scope_type == OfficialJurisdictionAssignment.ScopeType.DISTRICT:
        return assignment.district_id == property_record.district_id
    if assignment.scope_type == OfficialJurisdictionAssignment.ScopeType.WARD:
        return assignment.ward_id == property_record.ward_id
    return False
