import hashlib
import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import SensitiveConfirmation

DEFAULT_CONFIRMATION_LIFETIME = timedelta(minutes=15)


def _digest(raw_token):
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def issue_confirmation(*, user, purpose, subject_type="", subject_id="", recipient="", lifetime=DEFAULT_CONFIRMATION_LIFETIME):
    """Create a single-use confirmation and return its raw token exactly once."""
    raw_token = secrets.token_urlsafe(32)
    confirmation = SensitiveConfirmation.objects.create(
        user=user,
        purpose=purpose,
        subject_type=subject_type,
        subject_id=str(subject_id),
        recipient=recipient,
        token_digest=_digest(raw_token),
        expires_at=timezone.now() + lifetime,
    )
    return confirmation, raw_token


@transaction.atomic
def consume_confirmation(*, confirmation_id, raw_token, user, purpose):
    try:
        confirmation = SensitiveConfirmation.objects.select_for_update().get(
            pk=confirmation_id,
            user=user,
            purpose=purpose,
        )
    except SensitiveConfirmation.DoesNotExist:
        return False
    expected = _digest(raw_token)
    if confirmation.consumed_at or confirmation.expires_at <= timezone.now():
        return False
    if not secrets.compare_digest(confirmation.token_digest, expected):
        return False
    confirmation.consumed_at = timezone.now()
    confirmation.save(update_fields=["consumed_at"])
    return True


def link_state(confirmation, raw_token, purposes):
    """Describe a link opened by someone who may not be signed in.

    Returns "invalid" for an unknown id, wrong token or purpose (never
    revealing which), otherwise "used", "expired" or "valid".
    """
    if (
        confirmation is None
        or confirmation.purpose not in purposes
        or not raw_token
        or not secrets.compare_digest(confirmation.token_digest, _digest(raw_token))
    ):
        return "invalid"
    if confirmation.consumed_at:
        return "used"
    if confirmation.expires_at <= timezone.now():
        return "expired"
    return "valid"


@transaction.atomic
def decide_link_confirmation(*, confirmation_id, raw_token, purposes, decision, request=None):
    """Consume a link once and store the decision with its time, IP and browser (SRD 20.3).

    Returns (state, confirmation); the confirmation is only consumed when state is "valid".
    """
    confirmation = SensitiveConfirmation.objects.select_for_update().filter(pk=confirmation_id).first()
    state = link_state(confirmation, raw_token, purposes)
    if state != "valid":
        return state, confirmation
    confirmation.consumed_at = timezone.now()
    confirmation.decision = decision
    if request is not None:
        confirmation.ip_address = request.META.get("REMOTE_ADDR") or None
        confirmation.user_agent = request.META.get("HTTP_USER_AGENT", "")[:2000]
    confirmation.save(update_fields=["consumed_at", "decision", "ip_address", "user_agent"])
    return state, confirmation
