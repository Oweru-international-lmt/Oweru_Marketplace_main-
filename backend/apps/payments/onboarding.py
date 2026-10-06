from django.db import transaction
from rest_framework.exceptions import ValidationError
from apps.accounts.models import User
from apps.lister_identity.models import ListerIdentity
from apps.lister_identity.services import is_lister_identity_verified
from apps.roles.services import user_has_role
from apps.roles.legacy_authorization.services import _authorize, _assign, _role


@transaction.atomic
def enable_lister_actions(*, actor, user_id, role_code, request=None):
    """Explicit Management onboarding; never an alternative runtime grant.

    Canonical role/identity is required domain context. Only the explicit
    permission-bearing assignment grants new endpoint actions.
    """
    accounts = {u.pk: u for u in User.objects.select_for_update().filter(pk__in=[actor.pk, user_id]).order_by("pk")}
    if actor.pk not in accounts or user_id not in accounts:
        raise ValidationError("A persisted Management actor and lister are required.")
    actor, user = accounts[actor.pk], accounts[user_id]
    _authorize(actor, "authorization.assign_role")
    if role_code not in {"owner", "agent"} or user.account_category != "public" or not user.is_active or actor.pk == user.pk:
        raise ValidationError("Only active public Owner/Agent listers may be enabled.")
    if not user_has_role(user, role_code):
        raise ValidationError("The matching existing Marketplace lister relationship is required.")
    identity = ListerIdentity.objects.filter(user=user).first()
    if not is_lister_identity_verified(identity):
        raise ValidationError("Approved unexpired lister identity is required.")
    return _assign(user, _role(role_code), actor, request)
