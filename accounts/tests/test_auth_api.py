from datetime import timedelta

import pytest
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.auth_services import authenticate_phone_password
from accounts.models import User


pytestmark = pytest.mark.django_db


def register(client=None, **overrides):
    client = client or APIClient()
    data = {"phone": "+255700123456", "full_name": "Asha Mushi", "password": "Strong-pass-482!", "language": "sw"}
    data.update(overrides)
    return client.post("/api/v1/auth/register/", data, format="json")


def test_registration_hashes_password_and_returns_public_fields():
    response = register(email="asha@example.test", language="en")
    assert response.status_code == 201
    user = User.objects.get(phone="+255700123456")
    assert user.check_password("Strong-pass-482!")
    assert user.password != "Strong-pass-482!"
    assert response.data["language"] == "en"
    assert response.data["email"] == "asha@example.test"
    assert "password" not in response.data
    assert "failed_login_attempts" not in response.data
    assert "locked_until" not in response.data


def test_registration_optional_email_defaults_to_none():
    response = register()
    assert response.status_code == 201
    assert User.objects.get().email is None


def test_duplicate_phone_is_rejected():
    register()
    response = register(full_name="Duplicate")
    assert response.status_code == 400
    assert User.objects.count() == 1


@pytest.mark.parametrize("password", ["short", "password", "12345678"])
def test_weak_password_is_rejected(password):
    response = register(password=password)
    assert response.status_code == 400
    assert "password" in response.data


def test_login_issues_jwt_and_me_requires_authentication():
    register()
    client = APIClient()
    response = client.post("/api/v1/auth/login/", {"phone": "+255700123456", "password": "Strong-pass-482!"}, format="json")
    assert response.status_code == 200
    assert response.data["access"] and response.data["refresh"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    me = client.get("/api/v1/auth/me/")
    assert me.status_code == 200
    assert me.data["phone"] == "+255700123456"
    assert "password" not in me.data
    assert APIClient().get("/api/v1/auth/me/").status_code == 401


def test_invalid_login_counts_failed_attempts():
    register()
    response = APIClient().post("/api/v1/auth/login/", {"phone": "+255700123456", "password": "wrong"}, format="json")
    assert response.status_code == 400
    assert User.objects.get().failed_login_attempts == 1


def test_fifth_failure_locks_for_fifteen_minutes_and_hides_lock_details():
    register()
    user = User.objects.get()
    for _ in range(5):
        response = APIClient().post("/api/v1/auth/login/", {"phone": user.phone, "password": "wrong"}, format="json")
    user.refresh_from_db()
    assert user.failed_login_attempts == 5
    assert 14 * 60 <= (user.locked_until - timezone.now()).total_seconds() <= 15 * 60
    assert response.data == {"detail": "Invalid phone or password."}
    assert "locked_until" not in str(response.data)


def test_locked_account_cannot_login_until_lock_expires():
    register()
    user = User.objects.get()
    user.failed_login_attempts = 5
    user.locked_until = timezone.now() + timedelta(minutes=5)
    user.save(update_fields=["failed_login_attempts", "locked_until"])
    assert authenticate_phone_password(user.phone, "Strong-pass-482!") is None


def test_login_succeeds_after_lockout_expires_and_resets_counter():
    register()
    user = User.objects.get()
    user.failed_login_attempts = 5
    user.locked_until = timezone.now() - timedelta(seconds=1)
    user.save(update_fields=["failed_login_attempts", "locked_until"])
    assert authenticate_phone_password(user.phone, "Strong-pass-482!") == user
    user.refresh_from_db()
    assert user.failed_login_attempts == 0
    assert user.locked_until is None


def test_jwt_refresh_works():
    register()
    user = User.objects.get()
    refresh = RefreshToken.for_user(user)
    refreshed = APIClient().post("/api/v1/auth/token/refresh/", {"refresh": str(refresh)}, format="json")
    assert refreshed.status_code == 200
    assert refreshed.data["access"]


def test_password_reset_emails_a_single_use_link_and_changes_password():
    register(email="asha@example.test")
    client = APIClient()
    response = client.post("/api/v1/auth/password/reset/", {"phone": "+255700123456"}, format="json")
    assert response.status_code == 200
    assert len(mail.outbox) == 1
    user = User.objects.get()
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    confirmation = client.post("/api/v1/auth/password/reset/confirm/", {"uid": uid, "token": token, "new_password": "Other-Strong-992!"}, format="json")
    assert confirmation.status_code == 200
    user.refresh_from_db()
    assert user.check_password("Other-Strong-992!")
    assert not default_token_generator.check_token(user, token)


def test_password_reset_response_supports_accounts_without_email():
    register()
    response = APIClient().post("/api/v1/auth/password/reset/", {"phone": "+255700123456"}, format="json")
    assert response.status_code == 200
    assert "WhatsApp" in response.data["detail"]
    assert not mail.outbox


def test_password_reset_is_non_enumerating_for_unknown_phone():
    response = APIClient().post("/api/v1/auth/password/reset/", {"phone": "+255700999999"}, format="json")
    assert response.status_code == 200
    assert "If the account has an email address" in response.data["detail"]
