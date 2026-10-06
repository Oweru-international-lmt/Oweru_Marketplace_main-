from apps.accounts.models import User
from rest_framework.exceptions import PermissionDenied


def authorize(actor, permission):
    """The permission-bearing store is the sole action grant source."""
    if not actor or not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Authentication is required.")
    actor = User.objects.filter(pk=actor.pk, is_active=True).first()
    if actor is None or not actor.has_marketplace_permission(permission):
        raise PermissionDenied("The required Marketplace permission is missing.")
    return actor


def management(actor):
    return actor.account_category == "operational" and actor.has_role("management")


def lead_scope(actor, queryset):
    return queryset if management(actor) else queryset.filter(lister=actor)


def require_lister(actor, lead, permission="lead.update"):
    actor = authorize(actor, permission)
    if lead.lister_id != actor.pk:
        raise PermissionDenied("Only the relevant lister may perform this action.")
    return actor
