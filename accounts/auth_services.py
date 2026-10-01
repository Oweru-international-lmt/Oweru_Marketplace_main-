from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User

MAX_LOGIN_FAILURES = 5
LOCKOUT_DURATION = timedelta(minutes=15)
_DUMMY_PASSWORD_HASH = make_password("not-a-real-user-password")


def authenticate_phone_password(phone, password):
    """Validate credentials and apply a database-backed 5-attempt lockout."""
    normalized_phone = phone.strip()
    with transaction.atomic():
        try:
            user = User.objects.select_for_update().get(phone=normalized_phone)
        except User.DoesNotExist:
            check_password(password, _DUMMY_PASSWORD_HASH)
            return None

        now = timezone.now()
        had_failure_state = bool(user.failed_login_attempts or user.locked_until)
        if not user.is_active:
            check_password(password, user.password)
            return None
        if user.locked_until and user.locked_until > now:
            check_password(password, user.password)
            return None
        if user.locked_until and user.locked_until <= now:
            user.failed_login_attempts = 0
            user.locked_until = None

        if user.check_password(password):
            if had_failure_state:
                user.failed_login_attempts = 0
                user.locked_until = None
                user.save(update_fields=["failed_login_attempts", "locked_until", "updated_at"])
            return user

        user.failed_login_attempts = min(user.failed_login_attempts + 1, MAX_LOGIN_FAILURES)
        if user.failed_login_attempts >= MAX_LOGIN_FAILURES:
            user.locked_until = now + LOCKOUT_DURATION
        user.save(update_fields=["failed_login_attempts", "locked_until", "updated_at"])
        return None


def issue_jwt_pair(user):
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}
