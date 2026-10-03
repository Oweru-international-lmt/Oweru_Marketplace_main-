from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import override_settings
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.audit_events import (
    ACCOUNT_DELETION_REQUESTED,
    ACCOUNT_LOCKED,
    ACCOUNT_REGISTERED,
    EMAIL_VERIFIED,
    LOGIN_FAILED,
    LOGOUT,
    PASSWORD_CHANGED,
    PASSWORD_RESET_COMPLETED,
)
from apps.accounts.auth_services import authenticate_email_password
from apps.accounts.confirmations import format_confirmation_token, issue_confirmation
from apps.accounts.email_verification import EMAIL_VERIFICATION_PURPOSE
from apps.accounts.models import AccountDeletionRequest, SensitiveConfirmation, User
from apps.audit.models import AuditLog


pytestmark = pytest.mark.django_db


def register(client=None, **overrides):
    client = client or APIClient()
    data = {
        "email": "asha@example.test",
        "phone": "+255700123456",
        "full_name": "Asha Mushi",
        "password": "Strong-pass-482!",
        "preferred_language": "sw",
    }
    data.update(overrides)
    return client.post("/api/v1/auth/register/", data, format="json")


def login(email="asha@example.test", password="Strong-pass-482!"):
    return APIClient().post("/api/v1/auth/login/", {"email": email, "password": password}, format="json")


def authenticated_client(access):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


def latest_email_verification_token():
    url = mail.outbox[-1].body.rsplit(" ", 1)[-1]
    return parse_qs(urlparse(url).query)["token"][0]


def test_registration_hashes_password_and_returns_public_fields():
    response = register(preferred_language="en")
    assert response.status_code == 201
    user = User.objects.get(email="asha@example.test")
    assert user.check_password("Strong-pass-482!")
    assert user.password != "Strong-pass-482!"
    assert response.data["preferred_language"] == "en"
    assert response.data["email"] == "asha@example.test"
    assert response.data["phone"] == "+255700123456"
    assert response.data["is_email_verified"] is False
    assert "password" not in response.data
    assert "failed_login_attempts" not in response.data
    assert "locked_until" not in response.data
    assert "email_verified_at" not in response.data


@pytest.mark.parametrize("missing", ["email", "phone"])
def test_registration_requires_email_and_phone(missing):
    data = {"email": "asha@example.test", "phone": "+255700123456", "full_name": "Asha", "password": "Strong-pass-482!"}
    del data[missing]
    response = APIClient().post("/api/v1/auth/register/", data, format="json")
    assert response.status_code == 400
    assert missing in response.data


def test_registration_rejects_blank_full_name():
    response = register(full_name="   ")
    assert response.status_code == 400
    assert "full_name" in response.data


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
    assert me.data["is_email_verified"] is False
    assert "password" not in me.data
    assert APIClient().get("/api/v1/auth/me/").status_code == 401


def test_users_me_get_requires_authentication():
    response = APIClient().get("/api/v1/users/me/")

    assert response.status_code == 401


def test_users_me_get_returns_safe_private_profile_fields():
    register()
    tokens = login().data

    response = authenticated_client(tokens["access"]).get("/api/v1/users/me/")

    assert response.status_code == 200
    expected = {"id", "email", "phone", "full_name", "preferred_language", "is_email_verified", "created_at", "date_joined"}
    assert expected.issubset(response.data.keys())
    assert response.data["email"] == "asha@example.test"
    assert response.data["phone"] == "+255700123456"
    assert response.data["full_name"] == "Asha Mushi"
    assert response.data["preferred_language"] == "sw"
    assert response.data["is_email_verified"] is False
    sensitive = {
        "password",
        "failed_login_attempts",
        "locked_until",
        "email_verified_at",
        "is_staff",
        "is_superuser",
        "groups",
        "user_permissions",
        "roles",
        "permissions",
        "sensitive_confirmations",
    }
    assert sensitive.isdisjoint(response.data.keys())


def test_users_me_patch_requires_authentication():
    response = APIClient().patch("/api/v1/users/me/", {"full_name": "Asha Updated"}, format="json")

    assert response.status_code == 401


def test_users_me_patch_updates_full_name_and_trims_value():
    register()
    tokens = login().data

    response = authenticated_client(tokens["access"]).patch("/api/v1/users/me/", {"full_name": "  Asha Updated  "}, format="json")

    user = User.objects.get()
    assert response.status_code == 200
    assert response.data["full_name"] == "Asha Updated"
    assert user.full_name == "Asha Updated"


def test_users_me_patch_updates_preferred_language():
    register()
    tokens = login().data

    response = authenticated_client(tokens["access"]).patch("/api/v1/users/me/", {"preferred_language": "en"}, format="json")

    user = User.objects.get()
    assert response.status_code == 200
    assert response.data["preferred_language"] == "en"
    assert user.preferred_language == "en"


def test_users_me_patch_partial_update_succeeds():
    register()
    tokens = login().data

    response = authenticated_client(tokens["access"]).patch("/api/v1/users/me/", {"full_name": "Asha Partial"}, format="json")

    user = User.objects.get()
    assert response.status_code == 200
    assert user.full_name == "Asha Partial"
    assert user.preferred_language == "sw"


def test_users_me_patch_rejects_blank_full_name():
    register()
    tokens = login().data

    response = authenticated_client(tokens["access"]).patch("/api/v1/users/me/", {"full_name": "   "}, format="json")

    user = User.objects.get()
    assert response.status_code == 400
    assert "full_name" in response.data
    assert user.full_name == "Asha Mushi"


def test_users_me_patch_protected_fields_do_not_change():
    register()
    tokens = login().data
    user = User.objects.get()
    original = {
        "id": user.id,
        "email": user.email,
        "phone": user.phone,
        "password": user.password,
        "is_email_verified": user.is_email_verified,
        "email_verified_at": user.email_verified_at,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "failed_login_attempts": user.failed_login_attempts,
        "locked_until": user.locked_until,
    }

    response = authenticated_client(tokens["access"]).patch(
        "/api/v1/users/me/",
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "email": "changed@example.test",
            "phone": "+255700000000",
            "password": "Plaintext-should-not-apply",
            "is_email_verified": True,
            "email_verified_at": "2026-01-01T00:00:00Z",
            "is_staff": True,
            "is_superuser": True,
            "failed_login_attempts": 5,
            "locked_until": "2026-01-01T00:00:00Z",
            "roles": ["management"],
            "permissions": ["anything"],
        },
        format="json",
    )

    user.refresh_from_db()
    assert response.status_code == 200
    for field, value in original.items():
        assert getattr(user, field) == value
    assert "password" not in response.data
    assert "failed_login_attempts" not in response.data
    assert "locked_until" not in response.data


def test_users_me_patch_cannot_affect_another_user_profile():
    register()
    first_tokens = login().data
    register(email="zawadi@example.test", phone="+255700123457", full_name="Zawadi Mushi")
    other = User.objects.get(email="zawadi@example.test")

    response = authenticated_client(first_tokens["access"]).patch(
        "/api/v1/users/me/",
        {"id": str(other.id), "email": other.email, "phone": other.phone, "full_name": "Asha Only"},
        format="json",
    )

    other.refresh_from_db()
    first = User.objects.get(email="asha@example.test")
    assert response.status_code == 200
    assert first.full_name == "Asha Only"
    assert other.full_name == "Zawadi Mushi"
    assert other.phone == "+255700123457"


def test_auth_me_remains_compatible_read_only_profile():
    register()
    tokens = login().data
    client = authenticated_client(tokens["access"])

    response = client.get("/api/v1/auth/me/")
    patch = client.patch("/api/v1/auth/me/", {"full_name": "Should Not Apply"}, format="json")

    user = User.objects.get()
    assert response.status_code == 200
    assert response.data["email"] == "asha@example.test"
    assert response.data["is_email_verified"] is False
    assert "password" not in response.data
    assert patch.status_code == 405
    assert user.full_name == "Asha Mushi"


def test_account_deletion_request_requires_authentication():
    response = APIClient().post("/api/v1/users/me/deletion-request/", {"reason": "Please delete"}, format="json")

    assert response.status_code == 401


def test_authenticated_account_deletion_request_succeeds_and_keeps_user_active():
    register()
    tokens = login().data

    response = authenticated_client(tokens["access"]).post("/api/v1/users/me/deletion-request/", {}, format="json")

    user = User.objects.get()
    deletion_request = AccountDeletionRequest.objects.get()
    assert response.status_code == 201
    assert deletion_request.user == user
    assert deletion_request.status == AccountDeletionRequest.Status.PENDING
    assert user.is_active


def test_account_deletion_request_optional_reason_is_saved_and_returned():
    register()
    tokens = login().data

    response = authenticated_client(tokens["access"]).post(
        "/api/v1/users/me/deletion-request/",
        {"reason": "  I no longer need the service.  "},
        format="json",
    )

    deletion_request = AccountDeletionRequest.objects.get()
    assert response.status_code == 201
    assert deletion_request.reason == "I no longer need the service."
    assert response.data["reason"] == "I no longer need the service."


def test_account_deletion_request_response_exposes_safe_fields_only():
    register()
    tokens = login().data

    response = authenticated_client(tokens["access"]).post("/api/v1/users/me/deletion-request/", {}, format="json")

    assert response.status_code == 201
    assert set(response.data.keys()) == {"id", "status", "reason", "requested_at"}
    assert "user" not in response.data
    assert "reviewed_at" not in response.data
    assert "reviewed_by" not in response.data
    assert "review_note" not in response.data


def test_repeated_pending_account_deletion_request_does_not_duplicate():
    register()
    tokens = login().data
    client = authenticated_client(tokens["access"])

    first = client.post("/api/v1/users/me/deletion-request/", {"reason": "First"}, format="json")
    second = client.post("/api/v1/users/me/deletion-request/", {"reason": "Second"}, format="json")

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.data["id"] == second.data["id"]
    assert AccountDeletionRequest.objects.count() == 1
    assert AccountDeletionRequest.objects.get().reason == "First"


def test_account_deletion_request_cannot_target_another_user():
    register()
    first_tokens = login().data
    register(email="zawadi@example.test", phone="+255700123457", full_name="Zawadi Mushi")
    other = User.objects.get(email="zawadi@example.test")

    response = authenticated_client(first_tokens["access"]).post(
        "/api/v1/users/me/deletion-request/",
        {"user": str(other.id), "reason": "Try another user"},
        format="json",
    )

    first = User.objects.get(email="asha@example.test")
    deletion_request = AccountDeletionRequest.objects.get()
    assert response.status_code == 201
    assert deletion_request.user == first
    assert deletion_request.user != other


def test_account_deletion_request_ignores_protected_fields():
    register()
    tokens = login().data

    response = authenticated_client(tokens["access"]).post(
        "/api/v1/users/me/deletion-request/",
        {
            "status": AccountDeletionRequest.Status.APPROVED,
            "reviewed_at": "2026-01-01T00:00:00Z",
            "reviewed_by": "00000000-0000-0000-0000-000000000001",
            "review_note": "force approval",
            "user": "00000000-0000-0000-0000-000000000001",
            "reason": "Valid reason",
        },
        format="json",
    )

    deletion_request = AccountDeletionRequest.objects.get()
    assert response.status_code == 201
    assert deletion_request.status == AccountDeletionRequest.Status.PENDING
    assert deletion_request.reviewed_at is None
    assert deletion_request.reviewed_by is None
    assert deletion_request.review_note == ""
    assert deletion_request.user == User.objects.get()
    assert response.data["status"] == AccountDeletionRequest.Status.PENDING


@pytest.mark.parametrize(
    "status",
    [
        AccountDeletionRequest.Status.APPROVED,
        AccountDeletionRequest.Status.REJECTED,
        AccountDeletionRequest.Status.CANCELLED,
    ],
)
def test_historical_non_pending_request_does_not_prevent_new_request(status):
    register()
    user = User.objects.get()
    AccountDeletionRequest.objects.create(user=user, status=status, reason="historical")
    tokens = login().data

    response = authenticated_client(tokens["access"]).post("/api/v1/users/me/deletion-request/", {"reason": "new"}, format="json")

    assert response.status_code == 201
    assert AccountDeletionRequest.objects.count() == 2
    assert AccountDeletionRequest.objects.filter(user=user, status=AccountDeletionRequest.Status.PENDING).count() == 1


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


@override_settings(ACCOUNT_LOGIN_MAX_ATTEMPTS=3, ACCOUNT_LOGIN_LOCKOUT_MINUTES=7)
def test_login_lockout_uses_configured_threshold_and_duration():
    register()
    for _ in range(3):
        response = login(password="wrong")

    user = User.objects.get()
    assert user.failed_login_attempts == 3
    assert 6 * 60 <= (user.locked_until - timezone.now()).total_seconds() <= 7 * 60
    assert response.data == {"detail": "Invalid email or password."}


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


def test_unauthenticated_logout_is_rejected():
    response = APIClient().post("/api/v1/auth/logout/", {"refresh": "not-used"}, format="json")

    assert response.status_code == 401


def test_valid_logout_succeeds_and_blacklists_refresh():
    register()
    tokens = login().data

    response = authenticated_client(tokens["access"]).post("/api/v1/auth/logout/", {"refresh": tokens["refresh"]}, format="json")

    assert response.status_code == 200
    assert response.data == {"detail": "Logged out successfully."}
    assert BlacklistedToken.objects.count() == 1


def test_blacklisted_refresh_cannot_obtain_new_access_token():
    register()
    tokens = login().data
    authenticated_client(tokens["access"]).post("/api/v1/auth/logout/", {"refresh": tokens["refresh"]}, format="json")

    response = APIClient().post("/api/v1/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json")

    assert response.status_code == 401


def test_logout_rejects_malformed_refresh_token():
    register()
    tokens = login().data

    response = authenticated_client(tokens["access"]).post("/api/v1/auth/logout/", {"refresh": "not-a-refresh-token"}, format="json")

    assert response.status_code == 400
    assert response.data == {"detail": "Invalid refresh token."}
    assert BlacklistedToken.objects.count() == 0


def test_logout_rejects_another_users_refresh_token():
    register()
    first_tokens = login().data
    register(email="zawadi@example.test", phone="+255700123457", full_name="Zawadi Mushi")
    second_tokens = login(email="zawadi@example.test").data

    response = authenticated_client(first_tokens["access"]).post("/api/v1/auth/logout/", {"refresh": second_tokens["refresh"]}, format="json")

    assert response.status_code == 400
    assert response.data == {"detail": "Invalid refresh token."}
    assert BlacklistedToken.objects.count() == 0
    assert APIClient().post("/api/v1/auth/token/refresh/", {"refresh": second_tokens["refresh"]}, format="json").status_code == 200


def test_repeated_logout_is_handled_safely():
    register()
    tokens = login().data
    client = authenticated_client(tokens["access"])

    first = client.post("/api/v1/auth/logout/", {"refresh": tokens["refresh"]}, format="json")
    second = client.post("/api/v1/auth/logout/", {"refresh": tokens["refresh"]}, format="json")

    assert first.status_code == 200
    assert second.status_code == 200
    assert BlacklistedToken.objects.count() == 1


def password_change_payload(**overrides):
    data = {
        "current_password": "Strong-pass-482!",
        "new_password": "New-Strong-pass-994!",
        "new_password_confirm": "New-Strong-pass-994!",
    }
    data.update(overrides)
    return data


def test_unauthenticated_password_change_is_rejected():
    response = APIClient().post("/api/v1/auth/password/change/", password_change_payload(), format="json")

    assert response.status_code == 401


def test_password_change_with_correct_current_password_succeeds_and_hides_password_data():
    register()
    tokens = login().data

    response = authenticated_client(tokens["access"]).post("/api/v1/auth/password/change/", password_change_payload(), format="json")

    assert response.status_code == 200
    assert response.data == {"detail": "Credentials updated successfully."}
    assert "password" not in str(response.data).lower()
    assert "hash" not in str(response.data).lower()


def test_password_change_rejects_incorrect_current_password():
    register()
    tokens = login().data

    response = authenticated_client(tokens["access"]).post(
        "/api/v1/auth/password/change/",
        password_change_payload(current_password="wrong"),
        format="json",
    )

    assert response.status_code == 400
    assert "current_password" in response.data


def test_password_change_rejects_mismatched_new_passwords():
    register()
    tokens = login().data

    response = authenticated_client(tokens["access"]).post(
        "/api/v1/auth/password/change/",
        password_change_payload(new_password_confirm="Different-Strong-pass-994!"),
        format="json",
    )

    assert response.status_code == 400
    assert "new_password_confirm" in response.data


@pytest.mark.parametrize("new_password", ["password", "12345678"])
def test_password_change_rejects_weak_password(new_password):
    register()
    tokens = login().data

    response = authenticated_client(tokens["access"]).post(
        "/api/v1/auth/password/change/",
        password_change_payload(new_password=new_password, new_password_confirm=new_password),
        format="json",
    )

    assert response.status_code == 400
    assert "new_password" in response.data


def test_password_change_rejects_blank_password():
    register()
    tokens = login().data

    response = authenticated_client(tokens["access"]).post(
        "/api/v1/auth/password/change/",
        password_change_payload(new_password="", new_password_confirm=""),
        format="json",
    )

    assert response.status_code == 400
    assert "new_password" in response.data


def test_password_change_rejects_same_as_current_password():
    register()
    tokens = login().data

    response = authenticated_client(tokens["access"]).post(
        "/api/v1/auth/password/change/",
        password_change_payload(new_password="Strong-pass-482!", new_password_confirm="Strong-pass-482!"),
        format="json",
    )

    assert response.status_code == 400
    assert "new_password" in response.data


def test_password_change_updates_password_and_authentication_behavior():
    register()
    tokens = login().data

    response = authenticated_client(tokens["access"]).post("/api/v1/auth/password/change/", password_change_payload(), format="json")

    user = User.objects.get()
    assert response.status_code == 200
    assert user.check_password("New-Strong-pass-994!")
    assert login(password="Strong-pass-482!").status_code == 400
    assert login(password="New-Strong-pass-994!").status_code == 200


def test_password_change_blacklists_existing_refresh_tokens():
    register()
    tokens = login().data
    assert BlacklistedToken.objects.count() == 0

    response = authenticated_client(tokens["access"]).post("/api/v1/auth/password/change/", password_change_payload(), format="json")

    assert response.status_code == 200
    assert BlacklistedToken.objects.count() >= 1
    refresh = APIClient().post("/api/v1/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json")
    assert refresh.status_code == 401


def test_registration_creates_email_verification_token_and_email():
    response = register()

    assert response.status_code == 201
    user = User.objects.get()
    confirmation = SensitiveConfirmation.objects.get(user=user, purpose=EMAIL_VERIFICATION_PURPOSE)
    assert not user.is_email_verified
    assert user.email_verified_at is None
    assert confirmation.expires_at > timezone.now()
    assert confirmation.consumed_at is None
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [user.email]
    assert latest_email_verification_token().startswith(f"{confirmation.pk}:")


def test_valid_email_verification_succeeds_sets_timestamp_and_consumes_token():
    register()
    token = latest_email_verification_token()

    response = APIClient().post("/api/v1/auth/email/verify/", {"token": token}, format="json")

    user = User.objects.get()
    confirmation = SensitiveConfirmation.objects.get(purpose=EMAIL_VERIFICATION_PURPOSE)
    assert response.status_code == 200
    assert user.is_email_verified
    assert user.email_verified_at is not None
    assert confirmation.consumed_at is not None
    replay = APIClient().post("/api/v1/auth/email/verify/", {"token": token}, format="json")
    assert replay.status_code == 400


def test_invalid_email_verification_token_is_rejected():
    register()

    response = APIClient().post("/api/v1/auth/email/verify/", {"token": "not-a-real-token"}, format="json")

    user = User.objects.get()
    assert response.status_code == 400
    assert not user.is_email_verified


def test_expired_email_verification_token_is_rejected():
    user = User.objects.create_user(
        email="asha@example.test",
        phone="+255700123456",
        full_name="Asha Mushi",
        password="Strong-pass-482!",
    )
    confirmation, raw_token = issue_confirmation(
        user=user,
        purpose=EMAIL_VERIFICATION_PURPOSE,
        lifetime=timedelta(seconds=-1),
    )
    token = format_confirmation_token(confirmation, raw_token)

    response = APIClient().post("/api/v1/auth/email/verify/", {"token": token}, format="json")

    user.refresh_from_db()
    assert response.status_code == 400
    assert not user.is_email_verified


def test_email_verification_resend_replaces_pending_token():
    register()
    first_token = latest_email_verification_token()
    access = login().data["access"]

    response = authenticated_client(access).post("/api/v1/auth/email/resend/", {}, format="json")

    user = User.objects.get()
    assert response.status_code == 200
    assert SensitiveConfirmation.objects.filter(user=user, purpose=EMAIL_VERIFICATION_PURPOSE, consumed_at__isnull=True).count() == 1
    assert SensitiveConfirmation.objects.filter(user=user, purpose=EMAIL_VERIFICATION_PURPOSE, consumed_at__isnull=False).count() == 1
    assert len(mail.outbox) == 2
    assert APIClient().post("/api/v1/auth/email/verify/", {"token": first_token}, format="json").status_code == 400
    assert APIClient().post("/api/v1/auth/email/verify/", {"token": latest_email_verification_token()}, format="json").status_code == 200


def test_email_verification_resend_for_verified_user_is_safe():
    register()
    token = latest_email_verification_token()
    assert APIClient().post("/api/v1/auth/email/verify/", {"token": token}, format="json").status_code == 200
    access = login().data["access"]
    sent_count = len(mail.outbox)

    response = authenticated_client(access).post("/api/v1/auth/email/resend/", {}, format="json")

    user = User.objects.get()
    assert response.status_code == 200
    assert user.is_email_verified
    assert len(mail.outbox) == sent_count


def test_user_cannot_patch_email_verification_state():
    register()
    access = login().data["access"]

    response = authenticated_client(access).patch("/api/v1/auth/me/", {"is_email_verified": True}, format="json")

    user = User.objects.get()
    assert response.status_code == 405
    assert not user.is_email_verified


def test_password_reset_emails_a_single_use_link_and_changes_password():
    register()
    mail.outbox.clear()
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
    mail.outbox.clear()
    known = APIClient().post("/api/v1/auth/password/reset/", {"email": "asha@example.test"}, format="json")
    unknown = APIClient().post("/api/v1/auth/password/reset/", {"email": "nobody@example.test"}, format="json")
    assert unknown.status_code == known.status_code == 200
    assert unknown.data == known.data
    assert len(mail.outbox) == 1


def audit_payload_text(log):
    return f"{log.before} {log.after}".lower()


def latest_audit(action):
    return AuditLog.objects.filter(action=action).latest("created_at")


def test_registration_creates_expected_audit_event():
    response = register()

    user = User.objects.get()
    log = latest_audit(ACCOUNT_REGISTERED)
    assert response.status_code == 201
    assert log.actor == user
    assert log.entity_type == "User"
    assert log.entity_id == str(user.pk)
    assert log.after["account_category"] == "public"


def test_failed_login_creates_audit_event_without_password():
    register()

    response = login(password="wrong-secret")

    user = User.objects.get()
    log = latest_audit(LOGIN_FAILED)
    assert response.status_code == 400
    assert log.actor == user
    assert log.entity_id == str(user.pk)
    assert "wrong-secret" not in audit_payload_text(log)
    assert "password" not in audit_payload_text(log)


def test_unknown_failed_login_creates_safe_audit_event_without_password_or_enumeration():
    response = login(email="missing@example.test", password="wrong-secret")

    log = latest_audit(LOGIN_FAILED)
    assert response.status_code == 400
    assert response.data == {"detail": "Invalid email or password."}
    assert log.actor is None
    assert log.entity_id == ""
    assert log.after == {"account_resolved": False}
    assert "missing@example.test" not in audit_payload_text(log)
    assert "wrong-secret" not in audit_payload_text(log)


def test_lockout_creates_account_locked_once():
    register()

    for _ in range(5):
        login(password="wrong")
    login(password="wrong")

    assert AuditLog.objects.filter(action=LOGIN_FAILED).count() == 6
    assert AuditLog.objects.filter(action=ACCOUNT_LOCKED).count() == 1
    log = latest_audit(ACCOUNT_LOCKED)
    assert log.actor == User.objects.get()
    assert log.after["locked"] is True


def test_email_verification_creates_audit_event_without_token():
    register()
    token = latest_email_verification_token()

    response = APIClient().post("/api/v1/auth/email/verify/", {"token": token}, format="json")

    log = latest_audit(EMAIL_VERIFIED)
    assert response.status_code == 200
    assert log.actor == User.objects.get()
    assert "token" not in audit_payload_text(log)
    assert token.lower() not in audit_payload_text(log)


def test_invalid_email_verification_does_not_create_success_audit_event():
    register()

    response = APIClient().post("/api/v1/auth/email/verify/", {"token": "not-a-real-token"}, format="json")

    assert response.status_code == 400
    assert not AuditLog.objects.filter(action=EMAIL_VERIFIED).exists()


def test_successful_password_reset_creates_audit_event_without_secrets():
    register()
    mail.outbox.clear()
    client = APIClient()
    client.post("/api/v1/auth/password/reset/", {"email": "Asha@example.test"}, format="json")
    user = User.objects.get()
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    response = client.post(
        "/api/v1/auth/password/reset/confirm/",
        {"uid": uid, "token": token, "new_password": "Other-Strong-992!"},
        format="json",
    )

    log = latest_audit(PASSWORD_RESET_COMPLETED)
    assert response.status_code == 200
    assert log.actor == user
    payload = audit_payload_text(log)
    assert token.lower() not in payload
    assert "other-strong-992" not in payload
    assert "password" not in payload
    assert "hash" not in payload


def test_invalid_password_reset_does_not_create_success_audit_event():
    register()
    user = User.objects.get()
    uid = urlsafe_base64_encode(force_bytes(user.pk))

    response = APIClient().post(
        "/api/v1/auth/password/reset/confirm/",
        {"uid": uid, "token": "bad-token", "new_password": "Other-Strong-992!"},
        format="json",
    )

    assert response.status_code == 400
    assert not AuditLog.objects.filter(action=PASSWORD_RESET_COMPLETED).exists()


def test_password_change_creates_audit_event_without_passwords():
    register()
    tokens = login().data

    response = authenticated_client(tokens["access"]).post("/api/v1/auth/password/change/", password_change_payload(), format="json")

    log = latest_audit(PASSWORD_CHANGED)
    assert response.status_code == 200
    assert log.actor == User.objects.get()
    payload = audit_payload_text(log)
    assert "strong-pass-482" not in payload
    assert "new-strong-pass-994" not in payload
    assert "password" not in payload
    assert "hash" not in payload


def test_invalid_password_change_does_not_create_success_audit_event():
    register()
    tokens = login().data

    response = authenticated_client(tokens["access"]).post(
        "/api/v1/auth/password/change/",
        password_change_payload(current_password="wrong"),
        format="json",
    )

    assert response.status_code == 400
    assert not AuditLog.objects.filter(action=PASSWORD_CHANGED).exists()


def test_logout_creates_audit_event_without_jwt_contents():
    register()
    tokens = login().data

    response = authenticated_client(tokens["access"]).post("/api/v1/auth/logout/", {"refresh": tokens["refresh"]}, format="json")

    log = latest_audit(LOGOUT)
    assert response.status_code == 200
    assert log.actor == User.objects.get()
    payload = audit_payload_text(log)
    assert tokens["refresh"].lower() not in payload
    assert tokens["access"].lower() not in payload
    assert "jwt" not in payload
    assert "token" not in payload


def test_invalid_logout_does_not_create_success_audit_event():
    register()
    tokens = login().data

    response = authenticated_client(tokens["access"]).post("/api/v1/auth/logout/", {"refresh": "bad-refresh"}, format="json")

    assert response.status_code == 400
    assert not AuditLog.objects.filter(action=LOGOUT).exists()


def test_deletion_request_creates_audit_event():
    register()
    tokens = login().data

    response = authenticated_client(tokens["access"]).post("/api/v1/users/me/deletion-request/", {"reason": "Leaving"}, format="json")

    deletion_request = AccountDeletionRequest.objects.get()
    log = latest_audit(ACCOUNT_DELETION_REQUESTED)
    assert response.status_code == 201
    assert log.actor == User.objects.get()
    assert log.entity_type == "AccountDeletionRequest"
    assert log.entity_id == str(deletion_request.pk)
    assert log.after == {"status": "PENDING", "reason_provided": True}


def test_repeated_pending_deletion_request_does_not_create_duplicate_audit_event():
    register()
    tokens = login().data
    client = authenticated_client(tokens["access"])

    client.post("/api/v1/users/me/deletion-request/", {"reason": "First"}, format="json")
    response = client.post("/api/v1/users/me/deletion-request/", {"reason": "Second"}, format="json")

    assert response.status_code == 201
    assert AccountDeletionRequest.objects.count() == 1
    assert AuditLog.objects.filter(action=ACCOUNT_DELETION_REQUESTED).count() == 1
