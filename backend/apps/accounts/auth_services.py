from django.contrib.auth.hashers import check_password, make_password
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.exceptions import TokenBackendError, TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.state import token_backend
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from .audit_events import ACCOUNT_LOCKED, LOGOUT, PASSWORD_CHANGED, record_account_event, record_login_failed
from .managers import normalize_email_address
from .models import User

_DUMMY_PASSWORD_HASH = make_password("not-a-real-user-password")


def _login_max_attempts():
    return max(1, int(settings.ACCOUNT_LOGIN_MAX_ATTEMPTS))


def _lockout_duration():
    return timezone.timedelta(minutes=max(0, int(settings.ACCOUNT_LOGIN_LOCKOUT_MINUTES)))


def authenticate_email_password(email, password, *, request=None):
    """Validate credentials and apply the configured database-backed lockout."""
    normalized_email = normalize_email_address(email)
    max_attempts = _login_max_attempts()
    with transaction.atomic():
        try:
            user = User.objects.select_for_update().get(email=normalized_email)
        except User.DoesNotExist:
            check_password(password, _DUMMY_PASSWORD_HASH)
            record_login_failed(request=request)
            return None

        now = timezone.now()
        had_failure_state = bool(user.failed_login_attempts or user.locked_until)
        if not user.is_active:
            check_password(password, user.password)
            record_login_failed(user=user, request=request)
            return None
        if user.locked_until and user.locked_until > now:
            check_password(password, user.password)
            record_login_failed(user=user, request=request)
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

        user.failed_login_attempts = min(user.failed_login_attempts + 1, max_attempts)
        was_locked = bool(user.locked_until and user.locked_until > now)
        if user.failed_login_attempts >= max_attempts:
            user.locked_until = now + _lockout_duration()
        user.save(update_fields=["failed_login_attempts", "locked_until", "updated_at"])
        record_login_failed(user=user, request=request)
        if not was_locked and user.locked_until and user.locked_until > now:
            record_account_event(
                action=ACCOUNT_LOCKED,
                user=user,
                before={"failed_login_attempts": max(user.failed_login_attempts - 1, 0), "locked": False},
                after={"failed_login_attempts": user.failed_login_attempts, "locked": True},
                request=request,
            )
        return None


def issue_jwt_pair(user):
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}


def _decode_refresh_claims(raw_refresh):
    try:
        claims = token_backend.decode(raw_refresh, verify=True)
    except TokenBackendError:
        return None
    if claims.get(api_settings.TOKEN_TYPE_CLAIM) != RefreshToken.token_type:
        return None
    return claims


def _refresh_claims_belong_to_user(claims, user):
    return str(claims.get(api_settings.USER_ID_CLAIM)) == str(user.pk)


def _refresh_is_blacklisted(claims):
    jti = claims.get(api_settings.JTI_CLAIM)
    return bool(jti and BlacklistedToken.objects.filter(token__jti=jti).exists())


def blacklist_refresh_token_for_user(user, raw_refresh, *, request=None):
    try:
        refresh = RefreshToken(raw_refresh)
    except TokenError:
        claims = _decode_refresh_claims(raw_refresh)
        success = bool(claims and _refresh_claims_belong_to_user(claims, user) and _refresh_is_blacklisted(claims))
        if success:
            record_account_event(action=LOGOUT, user=user, after={"session_invalidated": True}, request=request)
        return success

    if str(refresh.get(api_settings.USER_ID_CLAIM)) != str(user.pk):
        return False
    refresh.blacklist()
    record_account_event(action=LOGOUT, user=user, after={"session_invalidated": True}, request=request)
    return True


@transaction.atomic
def change_user_password(user, new_password, *, request=None):
    user.set_password(new_password)
    user.save(update_fields=["password", "updated_at"])
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)
    record_account_event(action=PASSWORD_CHANGED, user=user, after={"sessions_invalidated": True}, request=request)
