from audit.services import record_event

from .models import Permission, Role, RolePermission, UserRole


def assign_role(*, user, role_code, assigned_by=None, request=None):
    role = Role.objects.get(code=role_code, is_active=True)
    assignment, created = UserRole.objects.get_or_create(user=user, role=role, defaults={"assigned_by": assigned_by})
    was_active = assignment.is_active
    if not created and not was_active:
        assignment.is_active = True
        assignment.assigned_by = assigned_by
        assignment.save(update_fields=["is_active", "assigned_by", "updated_at"])
    if created or not was_active:
        record_event(
            actor=assigned_by,
            action="role.assigned",
            entity_type="UserRole",
            entity_id=assignment.pk,
            before_state=None if created else {"user_id": str(user.pk), "role": role.code, "is_active": False},
            after_state={"user_id": str(user.pk), "role": role.code},
            request=request,
        )
    return assignment


def revoke_role(*, user, role_code, revoked_by=None, request=None):
    try:
        assignment = UserRole.objects.select_related("role").get(user=user, role__code=role_code, is_active=True)
    except UserRole.DoesNotExist:
        return False
    assignment.is_active = False
    assignment.save(update_fields=["is_active", "updated_at"])
    record_event(
        actor=revoked_by,
        action="role.revoked",
        entity_type="UserRole",
        entity_id=assignment.pk,
        before_state={"user_id": str(user.pk), "role": role_code, "is_active": True},
        after_state={"user_id": str(user.pk), "role": role_code, "is_active": False},
        request=request,
    )
    return True


def grant_permission(*, role_code, permission_code, permission_name, actor=None, request=None):
    role = Role.objects.get(code=role_code, is_active=True)
    permission, _ = Permission.objects.get_or_create(code=permission_code, defaults={"name": permission_name})
    relation, created = RolePermission.objects.get_or_create(role=role, permission=permission)
    if created:
        record_event(
            actor=actor,
            action="permission.granted",
            entity_type="RolePermission",
            entity_id=relation.pk,
            after_state={"role": role.code, "permission": permission.code},
            request=request,
        )
    return relation


def revoke_permission(*, role_code, permission_code, actor=None, request=None):
    try:
        relation = RolePermission.objects.select_related("role", "permission").get(role__code=role_code, permission__code=permission_code)
    except RolePermission.DoesNotExist:
        return False
    record_event(
        actor=actor,
        action="permission.revoked",
        entity_type="RolePermission",
        entity_id=relation.pk,
        before_state={"role": role_code, "permission": permission_code},
        request=request,
    )
    relation.delete()
    return True


def record_sensitive_access(*, actor, entity_type, entity_id, request=None):
    return record_event(actor=actor, action="sensitive_data.accessed", entity_type=entity_type, entity_id=entity_id, request=request)
