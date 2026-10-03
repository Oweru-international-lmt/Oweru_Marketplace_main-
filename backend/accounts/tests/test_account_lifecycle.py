"""M02/M03 leftovers: logout, profile edit, password change, temporary
passwords (ACC-06), email confirmation (ACC-05), phone confirmation link
(ACC-01, SRD 20.3), deletion requests (ACC-08) and the reset lifetime (ACC-03)."""
import re
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from django.conf import settings
from django.core import mail
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.account_services import issue_phone_confirmation
from accounts.models import AccountDeletionRequest, SensitiveConfirmation, User
from audit.models import AuditEvent
from authorization.services import assign_role, bootstrap_management

pytestmark = pytest.mark.django_db
PASSWORD = "Strong-pass-482!"
MANAGE = "/api/v1/management/accounts/"


def client(user=None):
    result = APIClient()
    if user:
        result.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return result


def register(email="buyer@test.test", phone="+255700000010"):
    data = {"email": email, "phone": phone, "full_name": "Buyer Person", "password": PASSWORD}
    assert APIClient().post("/api/v1/auth/register/", data, format="json").status_code == 201
    return User.objects.get(email=email)


@pytest.fixture
def manager():
    user = User.objects.create_superuser(email="manager@test.test", phone="1", full_name="Manager", password=PASSWORD)
    bootstrap_management(user=user)
    return user


@pytest.fixture
def buyer():
    return register()


def link_parts(text):
    query = parse_qs(urlparse(re.search(r"https?://\S+", text).group(0)).query)
    return query["id"][0], query["token"][0]


# ------------------------------------------------------------------ logout

def test_logout_revokes_refresh_token_and_is_idempotent(buyer):
    tokens = APIClient().post("/api/v1/auth/login/", {"email": buyer.email, "password": PASSWORD}, format="json").data
    assert APIClient().post("/api/v1/auth/logout/", {"refresh": tokens["refresh"]}, format="json").status_code == 204
    refreshed = APIClient().post("/api/v1/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json")
    assert refreshed.status_code == 401
    assert APIClient().post("/api/v1/auth/logout/", {"refresh": "not-a-token"}, format="json").status_code == 204


# ----------------------------------------------------------------- profile

def test_profile_update_requires_account_update_permission():
    roleless = User.objects.create_user(email="old@test.test", phone="5", full_name="Old", password=PASSWORD)
    assert client(roleless).patch("/api/v1/auth/me/", {"full_name": "New"}, format="json").status_code == 403


def test_profile_update_changes_allowed_fields_and_resets_phone_confirmation(buyer):
    User.objects.filter(pk=buyer.pk).update(phone_verified_at=timezone.now())
    response = client(buyer).patch(
        "/api/v1/auth/me/",
        {"full_name": "  Asha New ", "phone": "+255700000099", "language": "en", "email": "evil@test.test"},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["full_name"] == "Asha New"
    assert response.data["language"] == "en"
    assert response.data["email"] == "buyer@test.test"
    assert response.data["phone_verified"] is False
    event = AuditEvent.objects.filter(action="account.updated").latest("created_at")
    assert set(event.after_state["changed_fields"]) == {"full_name", "phone", "language"}
    assert "+255700000099" not in str(event.after_state)


def test_profile_phone_must_stay_unique(buyer):
    register(email="other@test.test", phone="+255700000011")
    response = client(buyer).patch("/api/v1/auth/me/", {"phone": "+255700000011"}, format="json")
    assert response.status_code == 400
    assert "phone" in response.data


# --------------------------------------------------------- password change

def test_password_change_checks_current_password_and_ends_old_sessions(buyer):
    old_refresh = RefreshToken.for_user(buyer)
    c = client(buyer)
    assert c.post("/api/v1/auth/password/change/", {"current_password": "wrong", "new_password": "Another-pass-551!"}).status_code == 400
    response = c.post("/api/v1/auth/password/change/", {"current_password": PASSWORD, "new_password": "Another-pass-551!"})
    assert response.status_code == 200
    assert response.data["access"] and response.data["refresh"]
    buyer.refresh_from_db()
    assert buyer.check_password("Another-pass-551!")
    assert APIClient().post("/api/v1/auth/token/refresh/", {"refresh": str(old_refresh)}).status_code == 401


def test_password_change_rejects_weak_or_same_password(buyer):
    c = client(buyer)
    assert c.post("/api/v1/auth/password/change/", {"current_password": PASSWORD, "new_password": "12345678"}).status_code == 400
    assert c.post("/api/v1/auth/password/change/", {"current_password": PASSWORD, "new_password": PASSWORD}).status_code == 400


# ------------------------------------------------- staff accounts (ACC-06)

def create_staff(manager, email="staff@test.test", phone="+255700000020"):
    response = client(manager).post(MANAGE, {"email": email, "phone": phone, "full_name": "Staff Person"}, format="json")
    assert response.status_code == 201, response.data
    return User.objects.get(pk=response.data["account"]["id"]), response.data["temporary_password"]


def test_management_creates_operational_account_with_temporary_password(manager):
    staff, temporary = create_staff(manager)
    assert staff.account_category == "operational"
    assert staff.must_change_password
    assert staff.check_password(temporary)
    assert not staff.user_roles.exists()
    assert AuditEvent.objects.filter(action="account.created", entity_id=str(staff.pk)).exists()
    assert temporary not in str(AuditEvent.objects.filter(action="account.created").values("after_state"))


def test_staff_account_creation_is_management_only_and_unique(manager, buyer):
    data = {"email": "x@test.test", "phone": "+255700000030", "full_name": "X"}
    assert APIClient().post(MANAGE, data, format="json").status_code == 401
    assert client(buyer).post(MANAGE, data, format="json").status_code == 403
    duplicate = client(manager).post(MANAGE, {**data, "email": "BUYER@test.test"}, format="json")
    assert duplicate.status_code == 400 and "email" in duplicate.data


def test_temporary_password_blocks_everything_except_profile_change_and_logout(manager):
    staff, temporary = create_staff(manager)
    assign_role(user=staff, role_code="verifier", assigned_by=manager)
    login = APIClient().post("/api/v1/auth/login/", {"email": staff.email, "password": temporary}, format="json").data
    assert login["user"]["must_change_password"] is True
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {login['access']}")
    assert c.get("/api/v1/auth/me/").status_code == 200
    blocked = c.get("/api/v1/auth/me/deletion-request/")
    assert blocked.status_code == 403 and blocked.data["detail"].code == "password_change_required"
    changed = c.post("/api/v1/auth/password/change/", {"current_password": temporary, "new_password": "Brand-new-pass-77!"})
    assert changed.status_code == 200 and changed.data["user"]["must_change_password"] is False
    fresh = APIClient()
    fresh.credentials(HTTP_AUTHORIZATION=f"Bearer {changed.data['access']}")
    assert fresh.get("/api/v1/auth/me/deletion-request/").status_code == 200


def test_management_edits_deactivates_and_reactivates_staff(manager):
    staff, _ = create_staff(manager)
    c = client(manager)
    assert c.patch(MANAGE + f"{staff.pk}/", {"full_name": "Renamed"}, format="json").data["full_name"] == "Renamed"
    assert c.post(MANAGE + f"{staff.pk}/deactivate/", {"reason": ""}, format="json").status_code == 400
    refresh = RefreshToken.for_user(staff)
    response = c.post(MANAGE + f"{staff.pk}/deactivate/", {"reason": "Left Oweru"}, format="json")
    assert response.status_code == 200 and response.data["is_active"] is False
    assert APIClient().post("/api/v1/auth/token/refresh/", {"refresh": str(refresh)}).status_code == 401
    assert c.post(MANAGE + f"{staff.pk}/reactivate/", {"reason": "Rejoined"}, format="json").data["is_active"] is True
    event = AuditEvent.objects.filter(action="account.deactivated").latest("created_at")
    assert event.after_state["reason"] == "Left Oweru"


def test_management_cannot_manage_public_self_or_management_accounts(manager, buyer):
    c = client(manager)
    assert c.post(MANAGE + f"{buyer.pk}/deactivate/", {"reason": "x"}, format="json").status_code == 400
    assert c.post(MANAGE + f"{manager.pk}/deactivate/", {"reason": "x"}, format="json").status_code == 403
    other_manager = User.objects.create_superuser(email="m2@test.test", phone="2", full_name="M2", password=PASSWORD)
    bootstrap_management(user=other_manager)
    assert c.post(MANAGE + f"{other_manager.pk}/deactivate/", {"reason": "x"}, format="json").status_code == 403


def test_management_issues_new_temporary_password(manager):
    staff, first = create_staff(manager)
    staff.must_change_password = False
    staff.save(update_fields=["must_change_password"])
    response = client(manager).post(MANAGE + f"{staff.pk}/temporary-password/")
    assert response.status_code == 200
    staff.refresh_from_db()
    assert staff.must_change_password and staff.check_password(response.data["temporary_password"])
    assert not staff.check_password(first)


# ------------------------------------------------- email confirmation (ACC-05)

def test_registration_sends_single_use_email_confirmation():
    register()
    assert len(mail.outbox) == 1
    confirmation_id, token = link_parts(mail.outbox[0].body)
    first = APIClient().post("/api/v1/auth/email/confirm/", {"id": confirmation_id, "token": token}, format="json")
    assert first.status_code == 200
    assert User.objects.get().email_verified_at is not None
    again = APIClient().post("/api/v1/auth/email/confirm/", {"id": confirmation_id, "token": token}, format="json")
    assert again.status_code == 400 and again.data["state"] == "used"


def test_email_confirmation_rejects_wrong_or_expired_token(buyer):
    confirmation_id, token = link_parts(mail.outbox[0].body)
    assert APIClient().post("/api/v1/auth/email/confirm/", {"id": confirmation_id, "token": token + "x"}, format="json").status_code == 400
    SensitiveConfirmation.objects.filter(pk=confirmation_id).update(expires_at=timezone.now() - timedelta(seconds=1))
    response = APIClient().post("/api/v1/auth/email/confirm/", {"id": confirmation_id, "token": token}, format="json")
    assert response.status_code == 400 and response.data["state"] == "expired"


def test_email_resend_only_while_unconfirmed(buyer):
    c = client(buyer)
    assert c.post("/api/v1/auth/email/resend/").status_code == 200
    assert len(mail.outbox) == 2
    User.objects.filter(pk=buyer.pk).update(email_verified_at=timezone.now())
    assert c.post("/api/v1/auth/email/resend/").status_code == 400


# ---------------------------------------- phone confirmation link (SRD 20.3)

def test_phone_confirmation_link_shows_masks_and_confirms_once(buyer):
    confirmation, link = issue_phone_confirmation(buyer)
    token = parse_qs(urlparse(link).query)["token"][0]
    path = f"/api/v1/auth/confirmations/{confirmation.pk}/"
    shown = APIClient().get(path, {"token": token})
    assert shown.status_code == 200 and shown.data["state"] == "valid"
    assert buyer.phone not in shown.data["recipient"]
    assert APIClient().get(path, {"token": "wrong"}).status_code == 404
    decided = APIClient().post(path, {"token": token, "decision": "confirmed"}, format="json", HTTP_USER_AGENT="TestBrowser")
    assert decided.status_code == 200
    buyer.refresh_from_db()
    assert buyer.phone_verified_at is not None
    confirmation.refresh_from_db()
    assert confirmation.decision == "confirmed" and confirmation.user_agent == "TestBrowser"
    assert APIClient().post(path, {"token": token, "decision": "confirmed"}, format="json").data["state"] == "used"


def test_declined_phone_link_does_not_confirm(buyer):
    confirmation, link = issue_phone_confirmation(buyer)
    token = parse_qs(urlparse(link).query)["token"][0]
    response = APIClient().post(f"/api/v1/auth/confirmations/{confirmation.pk}/", {"token": token, "decision": "declined"}, format="json")
    assert response.data["state"] == "declined"
    buyer.refresh_from_db()
    assert buyer.phone_verified_at is None


def test_email_links_are_not_served_by_the_whatsapp_page(buyer):
    confirmation_id, token = link_parts(mail.outbox[0].body)
    assert APIClient().get(f"/api/v1/auth/confirmations/{confirmation_id}/", {"token": token}).status_code == 404


def test_issue_phone_confirmation_command_prints_link(buyer, capsys):
    call_command("issue_phone_confirmation", "--user-id", str(buyer.pk))
    assert settings.CONFIRMATION_URL in capsys.readouterr().out


# ----------------------------------------------------- deletion (ACC-08)

def test_buyer_requests_views_and_cancels_deletion(buyer):
    c = client(buyer)
    created = c.post("/api/v1/auth/me/deletion-request/", {"reason": "Moving abroad"}, format="json")
    assert created.status_code == 201 and created.data["request"]["status"] == "pending"
    assert c.post("/api/v1/auth/me/deletion-request/", {}, format="json").status_code == 400
    assert c.get("/api/v1/auth/me/deletion-request/").data["request"]["reason"] == "Moving abroad"
    assert c.delete("/api/v1/auth/me/deletion-request/").status_code == 204
    assert c.get("/api/v1/auth/me/deletion-request/").data["request"]["status"] == "cancelled"
    assert c.delete("/api/v1/auth/me/deletion-request/").status_code == 404


def test_management_completes_deletion_by_deactivating_account(manager, buyer):
    deletion = client(buyer).post("/api/v1/auth/me/deletion-request/", {}, format="json").data["request"]
    refresh = RefreshToken.for_user(buyer)
    c = client(manager)
    listed = c.get(MANAGE + "deletion-requests/").data
    assert [row["id"] for row in listed] == [deletion["id"]]
    assert "email" not in listed[0]["account"] and "phone" not in listed[0]["account"]
    response = c.post(MANAGE + f"deletion-requests/{deletion['id']}/resolve/", {"decision": "completed"}, format="json")
    assert response.status_code == 200
    buyer.refresh_from_db()
    assert buyer.is_active is False
    assert User.objects.filter(pk=buyer.pk).exists()  # Records are kept.
    assert APIClient().post("/api/v1/auth/token/refresh/", {"refresh": str(refresh)}).status_code == 401
    again = c.post(MANAGE + f"deletion-requests/{deletion['id']}/resolve/", {"decision": "declined", "note": "x"}, format="json")
    assert again.status_code == 400


def test_declining_deletion_needs_a_note_and_keeps_account(manager, buyer):
    deletion = client(buyer).post("/api/v1/auth/me/deletion-request/", {}, format="json").data["request"]
    path = MANAGE + f"deletion-requests/{deletion['id']}/resolve/"
    assert client(manager).post(path, {"decision": "declined"}, format="json").status_code == 400
    assert client(manager).post(path, {"decision": "declined", "note": "Open deal"}, format="json").status_code == 200
    buyer.refresh_from_db()
    assert buyer.is_active
    assert AccountDeletionRequest.objects.get().resolution_note == "Open deal"


def test_deletion_queue_is_management_only(buyer):
    assert client(buyer).get(MANAGE + "deletion-requests/").status_code == 403


# ------------------------------------------------------- reset lifetime (ACC-03)

def test_email_reset_links_expire_after_thirty_minutes():
    assert settings.PASSWORD_RESET_TIMEOUT == 30 * 60
