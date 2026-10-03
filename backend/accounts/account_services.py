"""Self-service and Management account operations (ACC-03/05/06/08, ACC-01 phone link).

Every mutation and its audit event share one transaction. Audit states record
which fields changed, not contact values or passwords.
"""
import logging
import secrets

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from audit.services import record_event
from .confirmations import decide_link_confirmation, issue_confirmation
from .models import AccountDeletionRequest, SensitiveConfirmation, User

logger = logging.getLogger(__name__)

EMAIL_CONFIRMATION = "email_confirmation"
PHONE_CONFIRMATION = "phone_confirmation"
LINK_PURPOSES = frozenset({PHONE_CONFIRMATION})  # Purposes served by the public confirmation page.


def _link(base, confirmation, raw_token):
    separator = "&" if "?" in base else "?"
    return f"{base}{separator}id={confirmation.pk}&token={raw_token}"


def revoke_refresh_tokens(user):
    """Blacklist every refresh token issued to the user (sign-out everywhere)."""
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)


# ----------------------------------------------------------------- profile

PROFILE_FIELDS = ("full_name", "phone", "language")


@transaction.atomic
def update_profile(*, user, changes, request=None):
    user = User.objects.select_for_update().get(pk=user.pk)
    changed = [field for field in PROFILE_FIELDS if field in changes and changes[field] != getattr(user, field)]
    if not changed:
        return user
    for field in changed:
        setattr(user, field, changes[field])
    if "phone" in changed:
        # A new number has not been confirmed yet (ACC-01).
        user.phone_verified_at = None
    user.save()
    record_event(actor=user, action="account.updated", entity_type="User", entity_id=user.pk,
                 before_state={}, after_state={"changed_fields": changed}, request=request)
    return user


@transaction.atomic
def change_password(*, user, current_password, new_password, request=None):
    user = User.objects.select_for_update().get(pk=user.pk)
    if not user.check_password(current_password):
        raise ValidationError({"current_password": ["Your current password is incorrect."]})
    if current_password == new_password:
        raise ValidationError({"new_password": ["Choose a password different from your current one."]})
    try:
        validate_password(new_password, user=user)
    except DjangoValidationError as exc:
        raise ValidationError({"new_password": list(exc.messages)}) from exc
    was_temporary = user.must_change_password
    user.set_password(new_password)
    user.must_change_password = False
    user.save(update_fields=["password", "must_change_password", "updated_at"])
    # Old sessions end; the caller issues a fresh token pair for this one.
    revoke_refresh_tokens(user)
    record_event(actor=user, action="account.password_changed", entity_type="User", entity_id=user.pk,
                 after_state={"was_temporary": was_temporary}, request=request)
    return user


# ------------------------------------------------------- email confirmation

def send_email_confirmation(user):
    confirmation, raw_token = issue_confirmation(
        user=user,
        purpose=EMAIL_CONFIRMATION,
        subject_type="email",
        subject_id=user.email,
        recipient=user.email,
        lifetime=settings.EMAIL_CONFIRMATION_LIFETIME,
    )
    send_mail(
        subject="Confirm your Oweru Marketplace email",
        message=f"Open this link to confirm your email address: {_link(settings.EMAIL_CONFIRMATION_URL, confirmation, raw_token)}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
    return confirmation


def send_email_confirmation_safely(user):
    """Registration must not fail because a mail server is down."""
    try:
        send_email_confirmation(user)
    except Exception:
        logger.exception("Email confirmation delivery failed")


@transaction.atomic
def confirm_email(*, confirmation_id, raw_token, request=None):
    state, confirmation = decide_link_confirmation(
        confirmation_id=confirmation_id,
        raw_token=raw_token,
        purposes={EMAIL_CONFIRMATION},
        decision=SensitiveConfirmation.Decision.CONFIRMED,
        request=request,
    )
    if state != "valid":
        return state
    user = User.objects.select_for_update().get(pk=confirmation.user_id)
    if confirmation.subject_id != user.email:
        return "invalid"  # The address changed after the link was sent.
    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified_at", "updated_at"])
    record_event(actor=user, action="account.email_confirmed", entity_type="User", entity_id=user.pk, request=request)
    return "confirmed"


# ------------------------------------------------- phone confirmation link

def issue_phone_confirmation(user):
    """Create a WhatsApp confirmation link for the user's phone (ACC-01, SRD 20.3).

    The link must be sent from the staff WhatsApp outbox (M21) when a lister
    submits identity (M05); until then the issue_phone_confirmation command
    prints it.
    """
    confirmation, raw_token = issue_confirmation(
        user=user,
        purpose=PHONE_CONFIRMATION,
        subject_type="phone",
        subject_id=user.phone,
        recipient=user.phone,
        lifetime=settings.PHONE_CONFIRMATION_LIFETIME,
    )
    return confirmation, _link(settings.CONFIRMATION_URL, confirmation, raw_token)


@transaction.atomic
def decide_confirmation_link(*, confirmation_id, raw_token, decision, request=None):
    state, confirmation = decide_link_confirmation(
        confirmation_id=confirmation_id,
        raw_token=raw_token,
        purposes=LINK_PURPOSES,
        decision=decision,
        request=request,
    )
    if state != "valid":
        return state
    record_event(actor=None, action=f"confirmation.{decision}", entity_type="SensitiveConfirmation",
                 entity_id=confirmation.pk, after_state={"purpose": confirmation.purpose, "decision": decision},
                 request=request)
    if decision == SensitiveConfirmation.Decision.CONFIRMED and confirmation.purpose == PHONE_CONFIRMATION:
        user = User.objects.select_for_update().get(pk=confirmation.user_id)
        if confirmation.subject_id != user.phone:
            return "invalid"  # The number changed after the link was sent.
        user.phone_verified_at = timezone.now()
        user.save(update_fields=["phone_verified_at", "updated_at"])
    return decision


# --------------------------------------------------------- deletion (ACC-08)

@transaction.atomic
def request_deletion(*, user, reason="", request=None):
    user = User.objects.select_for_update().get(pk=user.pk)
    if user.deletion_requests.filter(status=AccountDeletionRequest.Status.PENDING).exists():
        raise ValidationError({"detail": "You already have a pending deletion request."})
    deletion = AccountDeletionRequest.objects.create(user=user, reason=reason.strip())
    record_event(actor=user, action="account.deletion_requested", entity_type="AccountDeletionRequest",
                 entity_id=deletion.pk, after_state={"status": deletion.status}, request=request)
    return deletion


@transaction.atomic
def cancel_deletion(*, user, request=None):
    deletion = (
        AccountDeletionRequest.objects.select_for_update()
        .filter(user=user, status=AccountDeletionRequest.Status.PENDING)
        .first()
    )
    if deletion is None:
        return None
    deletion.status = AccountDeletionRequest.Status.CANCELLED
    deletion.resolved_at = timezone.now()
    deletion.save(update_fields=["status", "resolved_at"])
    record_event(actor=user, action="account.deletion_cancelled", entity_type="AccountDeletionRequest",
                 entity_id=deletion.pk, before_state={"status": "pending"}, after_state={"status": deletion.status},
                 request=request)
    return deletion


@transaction.atomic
def resolve_deletion(*, deletion_id, actor, decision, note="", request=None):
    """Management decision. Completing deactivates the account and ends its
    sessions; records stay because some must be kept by law (ACC-08)."""
    from authorization.services import require_management_permission

    actor = User.objects.select_for_update().get(pk=actor.pk)
    require_management_permission(actor, "account.manage")
    try:
        deletion = AccountDeletionRequest.objects.select_for_update().get(pk=deletion_id)
    except AccountDeletionRequest.DoesNotExist:
        raise ValidationError({"detail": "Deletion request not found."})
    if deletion.status != AccountDeletionRequest.Status.PENDING:
        raise ValidationError({"detail": "This request has already been resolved."})
    if deletion.user_id == actor.pk:
        raise PermissionDenied("You cannot resolve your own deletion request.")
    if decision not in (AccountDeletionRequest.Status.COMPLETED, AccountDeletionRequest.Status.DECLINED):
        raise ValidationError({"decision": ["Choose completed or declined."]})
    if decision == AccountDeletionRequest.Status.DECLINED and not note.strip():
        raise ValidationError({"note": ["Give a reason when declining."]})
    deletion.status = decision
    deletion.resolved_at = timezone.now()
    deletion.resolved_by = actor
    deletion.resolution_note = note.strip()
    deletion.save(update_fields=["status", "resolved_at", "resolved_by", "resolution_note"])
    if decision == AccountDeletionRequest.Status.COMPLETED:
        target = User.objects.select_for_update().get(pk=deletion.user_id)
        target.is_active = False
        target.save(update_fields=["is_active", "updated_at"])
        revoke_refresh_tokens(target)
    record_event(actor=actor, action="account.deletion_resolved", entity_type="AccountDeletionRequest",
                 entity_id=deletion.pk, before_state={"status": "pending"},
                 after_state={"status": decision, "user_id": str(deletion.user_id)}, request=request)
    return deletion


# ------------------------------------------------- staff accounts (ACC-06)

def _management_target(actor, permission, user_id):
    from authorization.services import require_management_permission

    actor = User.objects.select_for_update().get(pk=actor.pk)
    require_management_permission(actor, permission)
    try:
        target = User.objects.select_for_update().get(pk=user_id)
    except User.DoesNotExist:
        raise ValidationError({"detail": "Account not found."})
    if target.pk == actor.pk:
        raise PermissionDenied("You cannot change your own account here.")
    if target.account_category != "operational":
        raise ValidationError({"detail": "Only staff and partner accounts are managed here."})
    if target.has_role("management"):
        raise PermissionDenied("Management accounts are changed through the setup process.")
    return actor, target


def temporary_password():
    # Readable once, long enough to resist guessing until it is replaced.
    return secrets.token_urlsafe(9)


@transaction.atomic
def create_staff_account(*, actor, email, phone, full_name, language="sw", request=None):
    from authorization.services import require_management_permission

    actor = User.objects.select_for_update().get(pk=actor.pk)
    require_management_permission(actor, "account.manage")
    password = temporary_password()
    user = User.objects.create_user(
        email=email,
        phone=phone,
        full_name=full_name,
        language=language,
        password=password,
        account_category="operational",
        must_change_password=True,
    )
    record_event(actor=actor, action="account.created", entity_type="User", entity_id=user.pk,
                 after_state={"account_category": "operational", "must_change_password": True}, request=request)
    return user, password


@transaction.atomic
def update_staff_account(*, actor, user_id, changes, request=None):
    actor, target = _management_target(actor, "account.manage", user_id)
    changed = [field for field in PROFILE_FIELDS if field in changes and changes[field] != getattr(target, field)]
    for field in changed:
        setattr(target, field, changes[field])
    if "phone" in changed:
        target.phone_verified_at = None
    if changed:
        target.save()
        record_event(actor=actor, action="account.updated", entity_type="User", entity_id=target.pk,
                     after_state={"changed_fields": changed}, request=request)
    return target


@transaction.atomic
def set_staff_account_active(*, actor, user_id, active, reason, request=None):
    actor, target = _management_target(actor, "account.suspend", user_id)
    if not reason.strip():
        raise ValidationError({"reason": ["Give a reason."]})
    if target.is_active == active:
        return target
    target.is_active = active
    target.save(update_fields=["is_active", "updated_at"])
    if not active:
        revoke_refresh_tokens(target)
    record_event(actor=actor, action="account.reactivated" if active else "account.deactivated",
                 entity_type="User", entity_id=target.pk, before_state={"is_active": not active},
                 after_state={"is_active": active, "reason": reason.strip()}, request=request)
    return target


@transaction.atomic
def reset_staff_password(*, actor, user_id, request=None):
    """Issue a new temporary password for a staff or partner account (ACC-06)."""
    actor, target = _management_target(actor, "account.manage", user_id)
    password = temporary_password()
    target.set_password(password)
    target.must_change_password = True
    target.failed_login_attempts = 0
    target.locked_until = None
    target.save(update_fields=["password", "must_change_password", "failed_login_attempts", "locked_until", "updated_at"])
    revoke_refresh_tokens(target)
    record_event(actor=actor, action="account.temporary_password_issued", entity_type="User", entity_id=target.pk,
                 request=request)
    return target, password
