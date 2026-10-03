import hashlib
import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import SensitiveConfirmation

DEFAULT_CONFIRMATION_LIFETIME = timedelta(minutes=15)
TOKEN_SEPARATOR = ":"


def format_confirmation_token(confirmation, raw_token):
    return f"{confirmation.pk}{TOKEN_SEPARATOR}{raw_token}"


def _split_confirmation_token(token):
    try:
        confirmation_id, raw_token = token.split(TOKEN_SEPARATOR, 1)
    except (AttributeError, ValueError):
        return None, None
    if not confirmation_id or not raw_token:
        return None, None
    return confirmation_id, raw_token


def issue_confirmation(*, user, purpose, subject_type="", subject_id="", lifetime=DEFAULT_CONFIRMATION_LIFETIME):
    """Create a single-use confirmation and return its raw token exactly once."""
    raw_token = secrets.token_urlsafe(32)
    confirmation = SensitiveConfirmation.objects.create(
        user=user,
        purpose=purpose,
        subject_type=subject_type,
        subject_id=str(subject_id),
        token_digest=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
        expires_at=timezone.now() + lifetime,
    )
    return confirmation, raw_token


def revoke_pending_confirmations(*, user, purpose):
    now = timezone.now()
    return SensitiveConfirmation.objects.filter(
        user=user,
        purpose=purpose,
        consumed_at__isnull=True,
        expires_at__gt=now,
    ).update(consumed_at=now)


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
    expected = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    if confirmation.consumed_at or confirmation.expires_at <= timezone.now():
        return False
    if not secrets.compare_digest(confirmation.token_digest, expected):
        return False
    confirmation.consumed_at = timezone.now()
    confirmation.save(update_fields=["consumed_at"])
    return True


@transaction.atomic
def consume_confirmation_token(*, token, purpose):
    confirmation_id, raw_token = _split_confirmation_token(token)
    if not confirmation_id:
        return None
    try:
        confirmation = SensitiveConfirmation.objects.select_for_update().select_related("user").get(
            pk=confirmation_id,
            purpose=purpose,
        )
    except (ValueError, SensitiveConfirmation.DoesNotExist):
        return None
    expected = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    if confirmation.consumed_at or confirmation.expires_at <= timezone.now():
        return None
    if not secrets.compare_digest(confirmation.token_digest, expected):
        return None
    confirmation.consumed_at = timezone.now()
    confirmation.save(update_fields=["consumed_at"])
    return confirmation
