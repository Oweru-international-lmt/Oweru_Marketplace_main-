from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError

from apps.roles.catalog import ROLE_AGENT, ROLE_MANAGEMENT, ROLE_OWNER
from apps.roles.services import user_has_role

from .models import PropertyRecord


def get_active_persisted_actor(actor):
    if actor is None or not getattr(actor, "is_authenticated", False):
        return None
    actor_id = getattr(actor, "pk", None)
    if not actor_id:
        return None

    User = get_user_model()
    try:
        return User.objects.get(pk=actor_id, is_active=True)
    except (TypeError, ValueError, DjangoValidationError, User.DoesNotExist):
        return None


def can_create_property_record(actor):
    actor = get_active_persisted_actor(actor)
    return bool(actor and (user_has_role(actor, ROLE_OWNER) or user_has_role(actor, ROLE_AGENT)))


def can_view_property_record(actor, property_record):
    actor = get_active_persisted_actor(actor)
    if actor is None or not isinstance(property_record, PropertyRecord):
        return False
    return property_record.created_by_id == actor.pk or user_has_role(actor, ROLE_MANAGEMENT)


def can_update_property_record(actor, property_record):
    return can_view_property_record(actor, property_record)


def get_accessible_property_records(actor):
    actor = get_active_persisted_actor(actor)
    queryset = PropertyRecord.objects.select_related("created_by", "region", "district", "ward", "locality")
    if actor is None:
        return queryset.none()
    if user_has_role(actor, ROLE_MANAGEMENT):
        return queryset
    return queryset.filter(created_by=actor)
