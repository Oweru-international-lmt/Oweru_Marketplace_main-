from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError

from apps.properties.models import PropertyRecord
from apps.roles.catalog import ROLE_AGENT, ROLE_MANAGEMENT, ROLE_OWNER
from apps.roles.services import user_has_role

from .models import Listing


def get_active_persisted_actor(actor):
    if actor is None or not getattr(actor, "is_authenticated", False):
        return None
    actor_id = getattr(actor, "pk", None)
    if not actor_id:
        return None

    User = get_user_model()
    if not isinstance(actor, User):
        return None
    try:
        return User.objects.get(pk=actor_id, is_active=True)
    except (TypeError, ValueError, DjangoValidationError, User.DoesNotExist):
        return None


def role_code_for_lister_kind(lister_kind):
    if lister_kind == Listing.ListerKind.OWNER:
        return ROLE_OWNER
    if lister_kind == Listing.ListerKind.AGENT:
        return ROLE_AGENT
    return None


def actor_has_lister_kind_role(actor, lister_kind):
    actor = get_active_persisted_actor(actor)
    role_code = role_code_for_lister_kind(lister_kind)
    return bool(actor and role_code and user_has_role(actor, role_code))


def can_create_listing(actor, *, lister_kind):
    return actor_has_lister_kind_role(actor, lister_kind)


def can_create_listing_for_property(actor, property_record):
    actor = get_active_persisted_actor(actor)
    return bool(actor and isinstance(property_record, PropertyRecord) and property_record.created_by_id == actor.pk)


def is_listing_lister(actor, listing):
    actor = get_active_persisted_actor(actor)
    return bool(actor and isinstance(listing, Listing) and listing.lister_id == actor.pk)


def can_view_listing(actor, listing):
    actor = get_active_persisted_actor(actor)
    return bool(
        actor
        and isinstance(listing, Listing)
        and (listing.lister_id == actor.pk or user_has_role(actor, ROLE_MANAGEMENT))
    )


def can_update_listing(actor, listing):
    return bool(is_listing_lister(actor, listing) and actor_has_lister_kind_role(actor, listing.lister_kind))


def can_activate_listing(actor, listing):
    return can_update_listing(actor, listing)


def can_withdraw_listing(actor, listing):
    return can_update_listing(actor, listing)


def can_suspend_listing(actor, listing):
    actor = get_active_persisted_actor(actor)
    return bool(actor and isinstance(listing, Listing) and user_has_role(actor, ROLE_MANAGEMENT))


def can_restore_listing(actor, listing):
    return can_suspend_listing(actor, listing)


def get_accessible_listings(actor):
    actor = get_active_persisted_actor(actor)
    queryset = Listing.objects.select_related("property", "lister")
    if actor is None:
        return queryset.none()
    if user_has_role(actor, ROLE_MANAGEMENT):
        return queryset
    return queryset.filter(lister=actor)
