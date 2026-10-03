from rest_framework.permissions import BasePermission

from .catalog import (
    ROLE_AGENT,
    ROLE_LOCAL_OFFICIAL,
    ROLE_MANAGEMENT,
    ROLE_MARKETER,
    ROLE_OWNER,
    ROLE_PROFESSIONAL,
    ROLE_VERIFIER,
)
from .services import user_has_role


def user_has_active_role(user, code):
    """Compatibility alias for the canonical service check."""
    return user_has_role(user, code)


class HasRole(BasePermission):
    role_code = None
    message = "You do not have the required role for this action."

    def has_permission(self, request, view):
        return bool(self.role_code and user_has_role(request.user, self.role_code))


class IsManagement(HasRole):
    role_code = ROLE_MANAGEMENT


class IsVerifier(HasRole):
    role_code = ROLE_VERIFIER


class IsMarketer(HasRole):
    role_code = ROLE_MARKETER


class IsProfessional(HasRole):
    role_code = ROLE_PROFESSIONAL


class IsLocalOfficial(HasRole):
    role_code = ROLE_LOCAL_OFFICIAL


class IsLister(BasePermission):
    message = "You must be an owner or agent to perform this action."

    def has_permission(self, request, view):
        return user_has_role(request.user, ROLE_OWNER) or user_has_role(request.user, ROLE_AGENT)


class DeferredDomainPermission(BasePermission):
    """Deny view and object access until a future domain policy is implemented."""

    message = "This domain permission is deferred until its domain policy is implemented."

    def has_permission(self, request, view):
        return False

    def has_object_permission(self, request, view, obj):
        return False


class IsListingOwner(DeferredDomainPermission):
    pass


class CanViewSensitiveOwnerData(DeferredDomainPermission):
    pass


class CanManageLead(DeferredDomainPermission):
    pass


class CanConfirmPayment(DeferredDomainPermission):
    pass


class CanManageVerification(DeferredDomainPermission):
    pass
