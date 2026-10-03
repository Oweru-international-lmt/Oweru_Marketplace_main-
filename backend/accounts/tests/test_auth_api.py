from datetime import timedelta

import pytest
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.auth_services import authenticate_email_password
from accounts.models import User


pytestmark = pytest.mark.django_db


def register(client=None, **overrides):
    client = client or APIClient()
    data = {
        "email": "asha@example.test",
        "phone": "+255700123456",
        "full_name": "Asha Mushi",
        "password": "Strong-pass-482!",
        "language": "sw",
    }
    data.update(overrides)
    return client.post("/api/v1/auth/register/", data, format="json")


def login(email="asha@example.test", password="Strong-pass-482!"):
    return APIClient().post("/api/v1/auth/login/", {"email": email, "password": password}, format="json")


def test_registration_hashes_password_and_returns_public_fields():
    response = register(language="en")
    assert response.status_code == 201
    user = User.objects.get(email="asha@example.test")
    assert user.check_password("Strong-pass-482!")
    assert user.password != "Strong-pass-482!"
    assert response.data["language"] == "en"
    assert response.data["email"] == "asha@example.test"
    assert response.data["phone"] == "+255700123456"
    assert "password" not in response.data
    assert "failed_login_attempts" not in response.data
    assert "locked_until" not in response.data


@pytest.mark.parametrize("missing", ["email", "phone"])
def test_registration_requires_email_and_phone(missing):
    data = {"email": "asha@example.test", "phone": "+255700123456", "full_name": "Asha", "password": "Strong-pass-482!"}
    del data[missing]
    response = APIClient().post("/api/v1/auth/register/", data, format="json")
    assert response.status_code == 400
    assert missing in response.data


def test_registration_stores_email_lowercased():
    register(email="  Asha@Example.TEST ")
    assert User.objects.get().email == "asha@example.test"


def test_duplicate_email_is_rejected_regardless_of_case():
    register()
    response = register(email="ASHA@example.test", phone="+255700123457")
    assert response.status_code == 400
    assert "email" in response.data
    assert User.objects.count() == 1


def test_duplicate_phone_is_rejected():
    register()
    response = register(email="other@example.test", full_name="Duplicate")
    assert response.status_code == 400
    assert "phone" in response.data
    assert User.objects.count() == 1


@pytest.mark.parametrize("password", ["short", "password", "12345678"])
def test_weak_password_is_rejected(password):
    response = register(password=password)
    assert response.status_code == 400
    assert "password" in response.data


def test_login_with_email_issues_jwt_and_me_requires_authentication():
    register()
    response = login()
    assert response.status_code == 200
    assert response.data["access"] and response.data["refresh"]
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    me = client.get("/api/v1/auth/me/")
    assert me.status_code == 200
    assert me.data["email"] == "asha@example.test"
    assert "password" not in me.data
    assert APIClient().get("/api/v1/auth/me/").status_code == 401


def test_login_email_is_case_insensitive():
    register()
    assert login(email="ASHA@Example.Test").status_code == 200


def test_login_rejects_phone_number():
    register()
    response = APIClient().post("/api/v1/auth/login/", {"phone": "+255700123456", "password": "Strong-pass-482!"}, format="json")
    assert response.status_code == 400


def test_invalid_login_counts_failed_attempts():
    register()
    response = login(password="wrong")
    assert response.status_code == 400
    assert User.objects.get().failed_login_attempts == 1


def test_fifth_failure_locks_for_fifteen_minutes_and_hides_lock_details():
    register()
    for _ in range(5):
        response = login(password="wrong")
    user = User.objects.get()
    assert user.failed_login_attempts == 5
    assert 14 * 60 <= (user.locked_until - timezone.now()).total_seconds() <= 15 * 60
    assert response.data == {"detail": "Invalid email or password."}
    assert "locked_until" not in str(response.data)


def test_locked_account_cannot_login_until_lock_expires():
    register()
    user = User.objects.get()
    user.failed_login_attempts = 5
    user.locked_until = timezone.now() + timedelta(minutes=5)
    user.save(update_fields=["failed_login_attempts", "locked_until"])
    assert authenticate_email_password(user.email, "Strong-pass-482!") is None


def test_login_succeeds_after_lockout_expires_and_resets_counter():
    register()
    user = User.objects.get()
    user.failed_login_attempts = 5
    user.locked_until = timezone.now() - timedelta(seconds=1)
    user.save(update_fields=["failed_login_attempts", "locked_until"])
    assert authenticate_email_password(user.email, "Strong-pass-482!") == user
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
    register()
    mail.outbox.clear()  # Drop the registration confirmation email.
    client = APIClient()
    response = client.post("/api/v1/auth/password/reset/", {"email": "Asha@example.test"}, format="json")
    assert response.status_code == 200
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["asha@example.test"]
    user = User.objects.get()
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    confirmation = client.post("/api/v1/auth/password/reset/confirm/", {"uid": uid, "token": token, "new_password": "Other-Strong-992!"}, format="json")
    assert confirmation.status_code == 200
    user.refresh_from_db()
    assert user.check_password("Other-Strong-992!")
    assert not default_token_generator.check_token(user, token)


def test_password_reset_is_non_enumerating_for_unknown_email():
    register()
    mail.outbox.clear()  # Drop the registration confirmation email.
    known = APIClient().post("/api/v1/auth/password/reset/", {"email": "asha@example.test"}, format="json")
    unknown = APIClient().post("/api/v1/auth/password/reset/", {"email": "nobody@example.test"}, format="json")
    assert unknown.status_code == known.status_code == 200
    assert unknown.data == known.data
    assert len(mail.outbox) == 1
