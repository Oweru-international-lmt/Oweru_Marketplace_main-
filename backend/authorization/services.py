from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import User
from audit.services import record_event
from .catalog import ASSIGNABLE_STAFF_ROLES, CATALOG, OPERATIONAL_ROLES, OPTIONAL_GRANTS, PUBLIC_ROLES
from .models import Permission, Role, RoleCode, RolePermission, UserRole


def _role(code, *, active=True):
    if code not in RoleCode.values:
        raise ValidationError({"role_code": "Unknown Marketplace role."})
    try:
        role = Role.objects.get(code=code)
    except Role.DoesNotExist:
        raise ValidationError({"role_code": "Role catalog has not been installed."})
    if active and not role.is_active:
        raise ValidationError({"role_code": "Role is inactive."})
    return role


def _lock_actor_target(actor, user=None):
    if actor is None or not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("An authorized actor is required.")
    ids = {actor.pk}
    if user is not None:
        ids.add(user.pk)
    locked = {u.pk: u for u in User.objects.select_for_update().filter(pk__in=ids).order_by("pk")}
    if actor.pk not in locked or (user is not None and user.pk not in locked):
        raise ValidationError("Account does not exist.")
    return locked[actor.pk], locked.get(user.pk) if user is not None else None


def _authorize(actor, permission):
    if actor.account_category != "operational" or not actor.has_role("management") or not actor.has_marketplace_permission(permission):
        raise PermissionDenied("Active Management and the required permission are necessary.")


def require_management_permission(actor, permission):
    """Public form of the Management check for other apps' governed services."""
    _authorize(actor, permission)


def _category(user, role):
    expected = "public" if role.code in PUBLIC_ROLES else "operational"
    opposite = OPERATIONAL_ROLES if expected == "public" else PUBLIC_ROLES
    if user.account_category != expected or user.user_roles.filter(role__code__in=opposite).exists():
        raise ValidationError("Public and operational roles must use separate accounts.")


def _assign(user, role, actor, request=None):
    if not user.is_active:
        raise ValidationError("Cannot assign a role to an inactive account.")
    _category(user, role)
    assignment, created = UserRole.objects.get_or_create(user=user, role=role, defaults={"assigned_by": actor})
    before = {"user_id": str(user.pk), "role": role.code, "is_active": False}
    if created or not assignment.is_active:
        assignment.is_active = True
        assignment.assigned_by = actor
        assignment.save(update_fields=["is_active", "assigned_by", "updated_at"])
        record_event(actor=actor, action="role.assigned", entity_type="UserRole", entity_id=assignment.pk,
                     before_state={} if created else before, after_state={**before, "is_active": True}, request=request)
    return assignment


@transaction.atomic
def register_public_user(*, request=None, **data):
    if set(data) - {"email", "phone", "full_name", "password", "language"}:
        raise ValidationError("Unsupported registration fields.")
    user = User.objects.create_user(**data, account_category="public")
    _assign(user, _role("buyer"), user, request)
    return user


@transaction.atomic
def assign_role(*, user, role_code, assigned_by=None, request=None):
    actor, user = _lock_actor_target(assigned_by, user)
    _authorize(actor, "authorization.assign_role")
    role = _role(role_code)
    if actor.pk == user.pk:
        raise PermissionDenied("Self-assignment is not allowed.")
    if role.code not in ASSIGNABLE_STAFF_ROLES:
        raise ValidationError("This role requires setup or a domain onboarding workflow.")
    return _assign(user, role, actor, request)


@transaction.atomic
def revoke_role(*, user, role_code, revoked_by=None, request=None):
    actor, user = _lock_actor_target(revoked_by, user)
    _authorize(actor, "authorization.revoke_role")
    role = _role(role_code, active=False)
    if actor.pk == user.pk:
        raise PermissionDenied("Self-revocation is not allowed.")
    if role.code not in OPERATIONAL_ROLES - {"management"}:
        raise ValidationError("This role is not managed by this workflow.")
    _category(user, role)
    assignment = UserRole.objects.filter(user=user, role=role, is_active=True).first()
    if assignment is None:
        return False
    assignment.is_active = False
    assignment.save(update_fields=["is_active", "updated_at"])
    state = {"user_id": str(user.pk), "role": role.code}
    record_event(actor=actor, action="role.revoked", entity_type="UserRole", entity_id=assignment.pk,
                 before_state={**state, "is_active": True}, after_state={**state, "is_active": False}, request=request)
    return True


def _optional_grant(actor, role_code, permission_code):
    _authorize(actor, "authorization.manage_outbox")
    role = _role(role_code)
    if permission_code not in CATALOG:
        raise ValidationError({"permission_code": "Unknown Marketplace permission."})
    if (role_code, permission_code) not in OPTIONAL_GRANTS:
        raise PermissionDenied("The canonical permission matrix is fixed policy.")
    role = Role.objects.select_for_update().get(pk=role.pk)
    try:
        permission = Permission.objects.get(code=permission_code)
    except Permission.DoesNotExist:
        raise ValidationError("Permission catalog has not been installed.")
    return role, permission


@transaction.atomic
def grant_permission(*, role_code, permission_code, permission_name=None, actor=None, request=None):
    actor, _ = _lock_actor_target(actor)
    role, permission = _optional_grant(actor, role_code, permission_code)
    relation, created = RolePermission.objects.get_or_create(role=role, permission=permission)
    if created:
        state = {"role": role.code, "permission": permission.code}
        record_event(actor=actor, action="permission.granted", entity_type="RolePermission", entity_id=relation.pk,
                     before_state={**state, "granted": False}, after_state={**state, "granted": True}, request=request)
    return relation


@transaction.atomic
def revoke_permission(*, role_code, permission_code, actor=None, request=None):
    actor, _ = _lock_actor_target(actor)
    role, permission = _optional_grant(actor, role_code, permission_code)
    relation = RolePermission.objects.filter(role=role, permission=permission).first()
    if relation is None:
        return False
    state = {"role": role.code, "permission": permission.code}
    record_event(actor=actor, action="permission.revoked", entity_type="RolePermission", entity_id=relation.pk,
                 before_state={**state, "granted": True}, after_state={**state, "granted": False}, request=request)
    relation.delete()
    return True


@transaction.atomic
def bootstrap_management(*, user):
    """Trusted deployment command only; never exposed through HTTP/admin."""
    user = User.objects.select_for_update().get(pk=user.pk)
    role = Role.objects.select_for_update().get(code="management", is_active=True)
    if not user.is_active or not user.is_staff or not user.is_superuser:
        raise PermissionDenied("Setup requires an active Django superuser.")
    return _assign(user, role, user)


def record_sensitive_access(*, actor, entity_type, entity_id, request=None):
    return record_event(actor=actor, action="sensitive_data.accessed", entity_type=entity_type, entity_id=entity_id, request=request)
