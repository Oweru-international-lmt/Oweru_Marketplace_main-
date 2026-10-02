from django.contrib import admin

from .models import Permission, Role, RolePermission, UserRole


class GovernanceAdmin(admin.ModelAdmin):
    actions = None

    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj) and request.user.has_role("management") and request.user.has_marketplace_permission("authorization.view")


@admin.register(Role)
class RoleAdmin(GovernanceAdmin):
    list_display = ("code", "name", "is_active")
    search_fields = ("code", "name")
    readonly_fields = ("code", "name", "description", "is_active", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Permission)
class PermissionAdmin(GovernanceAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")
    readonly_fields = ("code", "name", "description", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RolePermission)
class RolePermissionAdmin(GovernanceAdmin):
    list_display = ("role", "permission", "created_at")
    readonly_fields = ("role", "permission", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(UserRole)
class UserRoleAdmin(GovernanceAdmin):
    list_display = ("user", "role", "is_active", "assigned_by", "created_at")
    list_filter = ("role", "is_active")
    readonly_fields = ("user", "role", "is_active", "assigned_by", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
