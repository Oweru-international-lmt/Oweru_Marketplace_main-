from django.db import IntegrityError, transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.audit.services import create_audit_log

from .audit_events import ROLE_ASSIGNED, ROLE_REMOVED
from .catalog import CANONICAL_ROLE_DEFINITIONS, ROLE_MANAGEMENT
from .models import Role, UserRole
from .legacy_authorization import services as legacy_authorization_services


# Compatibility exports for M01/M02 and the legacy management API. Canonical
# role assignment/removal below intentionally does not write legacy tables.
bootstrap_management = legacy_authorization_services.bootstrap_management
grant_permission = legacy_authorization_services.grant_permission
record_sensitive_access = legacy_authorization_services.record_sensitive_access
register_public_user = legacy_authorization_services.register_public_user
revoke_permission = legacy_authorization_services.revoke_permission


def bootstrap_canonical_roles(*, role_model=None, using=None):
    model = role_model or Role
    manager = model.objects
    if using:
        manager = manager.using(using)
    roles = []
    for code, name in CANONICAL_ROLE_DEFINITIONS.items():
        role, _ = manager.get_or_create(code=code, defaults={"name": name})
        roles.append(role)
    return roles


def user_has_role(user, role_code):
    """Check active canonical assignments against persisted account/role state."""
    return bool(
        user
        and getattr(user, "is_authenticated", False)
        and user.is_active
        and role_code in CANONICAL_ROLE_DEFINITIONS
        and UserRole.objects.filter(
            user=user,
            user__is_active=True,
            role__code=role_code,
            role__is_active=True,
            is_active=True,
        ).exists()
    )


def _lock_actor_and_target(*, actor, user):
    if actor is None or not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("An authorized actor is required.")
    if not getattr(actor, "pk", None):
        raise PermissionDenied("A persisted authorized actor is required.")
    if user is None or not getattr(user, "pk", None):
        raise ValidationError("A persisted target user is required.")

    locked = {
        account.pk: account
        for account in User.objects.select_for_update().filter(pk__in={actor.pk, user.pk}).order_by("pk")
    }
    if actor.pk not in locked:
        raise PermissionDenied("A persisted authorized actor is required.")
    if user.pk not in locked:
        raise ValidationError("A persisted target user is required.")
    return locked[actor.pk], locked[user.pk]


def _require_role_management(actor):
    if not user_has_role(actor, ROLE_MANAGEMENT):
        raise PermissionDenied("Active Management role is required to manage roles.")


def _canonical_role(role_code, *, active=True):
    if role_code not in CANONICAL_ROLE_DEFINITIONS:
        raise ValidationError({"role_code": "Unknown canonical role."})
    try:
        role = Role.objects.select_for_update().get(code=role_code)
    except Role.DoesNotExist as exc:
        raise ValidationError({"role_code": "Canonical role catalog has not been installed."}) from exc
    if active and not role.is_active:
        raise ValidationError({"role_code": "Role is inactive."})
    return role


def _role_assignment_state(*, target, role, is_active):
    return {
        "user_id": str(target.pk),
        "role_code": role.code,
        "is_active": is_active,
    }


@transaction.atomic
def assign_role(*, user, role_code, assigned_by, request=None):
    actor, target = _lock_actor_and_target(actor=assigned_by, user=user)
    _require_role_management(actor)
    if actor.pk == target.pk:
        raise PermissionDenied("Self-assignment is not allowed.")
    if not target.is_active:
        raise ValidationError("Cannot assign a role to an inactive account.")

    role = _canonical_role(role_code)
    assignment = UserRole.objects.select_for_update().filter(user=target, role=role, is_active=True).first()
    if assignment is not None:
        return assignment

    try:
        with transaction.atomic():
            assignment = UserRole.objects.create(user=target, role=role, assigned_by=actor)
    except IntegrityError:
        return UserRole.objects.get(user=target, role=role, is_active=True)
    create_audit_log(
        actor=actor,
        action=ROLE_ASSIGNED,
        entity_type="UserRole",
        entity_id=assignment.pk,
        before={},
        after=_role_assignment_state(target=target, role=role, is_active=True),
        request=request,
    )
    return assignment


@transaction.atomic
def remove_role(*, user, role_code, removed_by, request=None):
    actor, target = _lock_actor_and_target(actor=removed_by, user=user)
    _require_role_management(actor)
    if actor.pk == target.pk:
        raise PermissionDenied("Self-removal is not allowed.")

    role = _canonical_role(role_code, active=False)
    assignment = UserRole.objects.select_for_update().filter(user=target, role=role, is_active=True).first()
    if assignment is None:
        return False
    before = _role_assignment_state(target=target, role=role, is_active=True)
    assignment.is_active = False
    assignment.save(update_fields=["is_active"])
    create_audit_log(
        actor=actor,
        action=ROLE_REMOVED,
        entity_type="UserRole",
        entity_id=assignment.pk,
        before=before,
        after=_role_assignment_state(target=target, role=role, is_active=False),
        request=request,
    )
    return True


def revoke_role(*, user, role_code, revoked_by, request=None):
    """Compatibility name for canonical role removal."""
    return remove_role(user=user, role_code=role_code, removed_by=revoked_by, request=request)
