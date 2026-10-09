import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .audit_events import EMAIL_VERIFIED, record_account_event
from .confirmations import consume_confirmation_token, format_confirmation_token, issue_confirmation, revoke_pending_confirmations

logger = logging.getLogger(__name__)

EMAIL_VERIFICATION_PURPOSE = "email_verification"


def _verification_lifetime():
    return timedelta(minutes=max(1, int(settings.ACCOUNT_EMAIL_VERIFICATION_MINUTES)))


def _verification_link(token):
    base_url = settings.EMAIL_VERIFICATION_URL
    if not base_url:
        return token
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}token={token}"


@transaction.atomic
def create_email_verification_token(user):
    if user.is_email_verified:
        return None
    revoke_pending_confirmations(user=user, purpose=EMAIL_VERIFICATION_PURPOSE)
    confirmation, raw_token = issue_confirmation(
        user=user,
        purpose=EMAIL_VERIFICATION_PURPOSE,
        lifetime=_verification_lifetime(),
    )
    return format_confirmation_token(confirmation, raw_token)


def send_email_verification(user):
    token = create_email_verification_token(user)
    if token is None:
        return None
    from apps.notifications.services import send_account_email
    send_account_email(user=user, purpose="EMAIL_VERIFICATION", link=_verification_link(token))
    return token


def send_email_verification_safely(user):
    try:
        return send_email_verification(user)
    except Exception:
        logger.exception("Email verification delivery failed")
        return None


@transaction.atomic
def verify_email_token(token, *, request=None):
    confirmation = consume_confirmation_token(token=token, purpose=EMAIL_VERIFICATION_PURPOSE)
    if confirmation is None:
        return False
    user = confirmation.user
    was_verified = user.is_email_verified
    if not user.is_email_verified:
        user.is_email_verified = True
        user.email_verified_at = timezone.now()
        user.save(update_fields=["is_email_verified", "email_verified_at", "updated_at"])
    revoke_pending_confirmations(user=user, purpose=EMAIL_VERIFICATION_PURPOSE)
    record_account_event(
        action=EMAIL_VERIFIED,
        user=user,
        before={"is_email_verified": was_verified},
        after={"is_email_verified": True},
        request=request,
    )
    return True
