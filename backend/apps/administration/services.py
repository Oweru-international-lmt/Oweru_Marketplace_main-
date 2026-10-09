from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.accounts.models import User
from apps.audit.services import create_audit_log
from apps.leads.policies import authorize, management
from apps.payments.idempotency import Conflict
from .models import AdministrationHistory


def require_manager(actor, permission="settings.manage"):
    actor = authorize(actor, permission)
    if not management(actor):
        raise PermissionDenied("Active Marketplace Management is required.")
    return actor


def history(actor, row, reason, before, after, request=None):
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        raise ValidationError("A recorded reason of at most 1000 characters is required.")
    record = AdministrationHistory.objects.create(actor=actor, entity_type=type(row).__name__, entity_id=row.pk, reason=reason.strip(), before=before, after=after)
    create_audit_log(actor=actor, action="administration.changed", entity_type=type(row).__name__, entity_id=row.pk, before=before, after={**after, "reason": reason.strip(), "history_id": str(record.pk)}, request=request)
    return record


@transaction.atomic
def account_change(*, actor, user_id, version, reason, active=None, full_name=None, request=None):
    actor = require_manager(actor, "account.suspend" if active is not None else "account.manage")
    from apps.roles.legacy_authorization.models import UserRole
    ids = set(UserRole.objects.filter(role__code="management", is_active=True).values_list("user_id", flat=True)) | {actor.pk, user_id}
    locked = {row.pk: row for row in User.objects.select_for_update().filter(pk__in=ids).order_by("pk")}
    actor = require_manager(locked.get(actor.pk), "account.suspend" if active is not None else "account.manage")
    row = get_object_or_404(User, pk=user_id)
    if version != row.administration_version:
        raise Conflict("Account changed; refresh before editing.")
    if active is not None and not isinstance(active, bool):
        raise ValidationError("Active must be a boolean.")
    if active is False and (row.pk == actor.pk or row.has_role("management") and sum(1 for item in locked.values() if item.is_active and item.has_role("management")) <= 1):
        raise PermissionDenied("Self-suspension and removal of the last active Management account are prohibited.")
    if full_name is not None and (row.account_category != "operational" or not isinstance(full_name, str) or not full_name.strip() or len(full_name) > 255):
        raise ValidationError("A valid operational-account name is required.")
    if active is None and full_name is None:
        raise ValidationError("Provide an account change.")
    before = {"is_active": row.is_active, "full_name": row.full_name, "version": row.administration_version}
    if active is not None:
        row.is_active = active
    if full_name is not None:
        row.full_name = full_name.strip()
    row.administration_version += 1
    row.save(update_fields=["is_active", "full_name", "administration_version", "updated_at"])
    history(actor, row, reason, before, {"is_active": row.is_active, "full_name": row.full_name, "version": row.administration_version}, request)
    return row


@transaction.atomic
def listing_change(*, actor, listing_id, version, reason, action, request=None):
    from apps.listings.models import Listing
    from apps.listings.services import suspend_listing, restore_listing
    actor = require_manager(actor, "listing.suspend")
    row = get_object_or_404(Listing.objects.select_for_update(), listing_id=listing_id)
    if row.updated_at.isoformat() != version:
        raise Conflict("Listing changed; refresh before acting.")
    if action == "suspend":
        row = suspend_listing(actor=actor, listing=row, reason=reason, request=request)
    elif action == "restore":
        row = restore_listing(actor=actor, listing=row, reason=reason, request=request)
    else:
        raise ValidationError("Unknown listing action.")
    return row


@transaction.atomic
def create_staff(*, actor, values, request=None):
    from apps.roles.services import assign_role
    from apps.roles.legacy_authorization.services import assign_role as assign_legacy
    from apps.notifications.services import emit
    actor = require_manager(actor, "account.manage")
    values = dict(values)
    role = values.pop("role")
    if role not in {"verifier", "marketer"}:
        raise ValidationError("Management accounts require trusted setup; partners use existing onboarding services.")
    from apps.free_checks.services import normalize_phone
    values["phone"] = normalize_phone(values["phone"])
    from apps.accounts.managers import normalize_email_address
    values["email"] = normalize_email_address(values["email"])
    row = User(account_category="operational", **values)
    row.set_unusable_password()
    from django.core.exceptions import ValidationError as ModelError
    try:
        row.full_clean()
    except ModelError as exc:
        raise ValidationError(exc.message_dict) from exc
    row.save()
    assign_role(user=row, role_code=role, assigned_by=actor, request=request)
    assign_legacy(user=row, role_code=role, assigned_by=actor, request=request)
    from django.conf import settings
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode
    from urllib.parse import urlencode
    if not settings.PASSWORD_RESET_URL:
        raise ValidationError("PASSWORD_RESET_URL is required before staff provisioning.")
    link = settings.PASSWORD_RESET_URL + ("&" if "?" in settings.PASSWORD_RESET_URL else "?") + urlencode({"uid": urlsafe_base64_encode(force_bytes(row.pk)), "token": default_token_generator.make_token(row)})
    from datetime import timedelta
    from django.utils import timezone
    emit(event_key=f"staff-created:{row.pk}", purpose="STAFF_LOGIN", channels=["email"], recipient=row, actor=actor, context={"details": row.email, "link": link}, source=row, expires_at=timezone.now() + timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT))
    history(actor, row, "Staff account created", {}, {"role": role, "account_category": "operational"}, request)
    return row
