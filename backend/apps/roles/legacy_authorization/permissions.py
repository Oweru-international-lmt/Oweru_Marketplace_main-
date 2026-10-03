from rest_framework.permissions import BasePermission

from apps.accounts.models import User


class HasMarketplaceRole(BasePermission):
    """Views set `required_role` to a database-backed role code."""

    message = "You do not have the required role for this action."

    def has_permission(self, request, view):
        code = getattr(view, "required_role", None)
        return bool(code and request.user and request.user.is_authenticated and request.user.has_role(code))


class HasMarketplacePermission(BasePermission):
    """Views set `required_marketplace_permission` to a Permission.code."""

    message = "You do not have permission to perform this action."

    def has_permission(self, request, view):
        code = getattr(view, "required_marketplace_permission", None)
        return bool(
            code
            and request.user
            and request.user.is_authenticated
            and request.user.has_marketplace_permission(code)
        )


class IsManagement(HasMarketplaceRole):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.has_role("management"))


class IsSelf(BasePermission):
    """Object check for account-owned resources exposing a `user_id`."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_active
                    and User.objects.filter(pk=request.user.pk, is_active=True).exists())

    def has_object_permission(self, request, view, obj):
        owner_id = getattr(obj, "user_id", getattr(obj, "id", None))
        return bool(self.has_permission(request, view) and owner_id is not None and owner_id == request.user.id)
