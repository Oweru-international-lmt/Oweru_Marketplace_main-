from datetime import timedelta
from unittest.mock import patch
import pytest
from django.utils import timezone
from django.db import connection, transaction, DatabaseError
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient
from apps.professionals.tests.test_professionals import account, storage
from apps.payments.idempotency import Conflict
from apps.payments.tests.test_concurrency import concurrent
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.administration import services
from apps.administration.models import AdministrationHistory
from apps.verification.configuration import change_setting, setting
from apps.verification.models import VerificationSetting

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("role", ["buyer", "owner", "agent", "local_official", "professional", "verifier", "marketer"])
def test_non_management_cannot_access_queues_settings_audit_or_accounts(role):
    user = account(role)
    client = APIClient()
    client.force_authenticate(user)
    for path in ["dashboard/", "settings/", "audit/"]:
        assert client.get("/api/v1/management/" + path).status_code == 403
    assert client.post("/api/v1/management/accounts/", {"role": "verifier", "email": "staff@example.test", "phone": "+255712345679", "full_name": "Staff"}, format="json").status_code == 403


def test_empty_dashboard_and_audit_are_management_only():
    manager = account("management")
    client = APIClient()
    client.force_authenticate(manager)
    dashboard = client.get("/api/v1/management/dashboard/")
    assert dashboard.status_code == 200
    assert dashboard.data["identities_to_approve"] == 0 and dashboard.data["outbox_waiting"] == 0
    assert "limitation" in dashboard.data["partner_approvals"]
    assert client.get("/api/v1/management/audit/").status_code == 200


def test_account_suspend_restore_reason_version_and_persisted_access():
    manager, buyer = account("management"), account("buyer")
    row = services.account_change(actor=manager, user_id=buyer.pk, version=1, reason="Policy violation", active=False)
    assert not row.is_active and row.administration_version == 2
    with pytest.raises(Conflict):
        services.account_change(actor=manager, user_id=buyer.pk, version=1, reason="stale", active=True)
    row = services.account_change(actor=manager, user_id=buyer.pk, version=2, reason="Review completed", active=True)
    assert row.is_active and AdministrationHistory.objects.count() == 2
    with pytest.raises(ValidationError):
        services.account_change(actor=manager, user_id=buyer.pk, version=3, reason="", active=False)
    buyer.refresh_from_db()
    assert buyer.is_active and buyer.administration_version == 3


def test_self_suspension_blocked_and_management_revocation_checked():
    manager = account("management")
    with pytest.raises(PermissionDenied):
        services.account_change(actor=manager, user_id=manager.pk, version=1, reason="self", active=False)
    User.objects.filter(pk=manager.pk).update(is_active=False)
    with pytest.raises(PermissionDenied):
        services.require_manager(manager)


def test_setting_cas_history_validation_and_runtime_identity_expiry():
    from apps.lister_identity.services import calculate_lister_identity_expires_at, add_calendar_months
    manager = account("management")
    row = change_setting(actor=manager, key="identity_expiry_months", value=3, expected_version=0)
    assert row.version == 1 and row.history.count() == 1
    now = timezone.now()
    assert calculate_lister_identity_expires_at(now) == add_calendar_months(now, 3)
    with pytest.raises(Conflict):
        change_setting(actor=manager, key="identity_expiry_months", value=4, expected_version=0)
    for value in [0, True, "NaN", {}, 1.5]:
        with pytest.raises(ValidationError):
            change_setting(actor=manager, key="free_check_daily_limit", value=value)
    with pytest.raises(ValidationError):
        change_setting(actor=manager, key="duplicate_size_percent", value=101)


def test_settings_api_requires_version_and_preserves_unconfigured_fee():
    manager = account("management")
    client = APIClient()
    client.force_authenticate(manager)
    result = client.get("/api/v1/management/settings/")
    assert result.status_code == 200
    assert next(item for item in result.data["settings"] if item["key"] == "full_check_fee")["value"] is None
    path = "/api/v1/management/settings/free_check_daily_limit/"
    assert client.put(path, {"value": 2}, format="json").status_code == 400
    assert client.put(path, {"value": 2, "version": 0}, format="json").status_code == 200
    assert client.put(path, {"value": 3, "version": 0}, format="json").status_code == 409
    assert len(client.get(path).data["history"]) == 1


def test_staff_creation_reuses_roles_without_exposing_credentials():
    manager = account("management")
    row = services.create_staff(actor=manager, values={"role": "verifier", "email": "new-staff@example.test", "phone": "+255712345679", "full_name": "New Staff"})
    assert row.account_category == "operational" and row.has_role("verifier")
    assert row.has_marketplace_permission("verification.record_result")
    assert not row.has_usable_password() and not row.is_superuser and not row.is_staff
    from apps.notifications.models import Notification
    notice = Notification.objects.get(purpose="STAFF_LOGIN")
    assert "token=" in notice.message
    assert notice.expires_at is not None
    assert "token" not in str(AuditLog.objects.filter(entity_id=str(row.pk)).values("before", "after"))
    with pytest.raises(ValidationError):
        services.create_staff(actor=manager, values={"role": "management", "email": "no@example.test", "phone": "+255712345680", "full_name": "No"})


def test_full_check_fee_requires_persisted_director_designation():
    manager = account("management")
    with pytest.raises(PermissionDenied):
        change_setting(actor=manager, key="full_check_fee", value="100000", expected_version=0)
    User.objects.filter(pk=manager.pk).update(management_position="DIRECTOR")
    row = change_setting(actor=manager, key="full_check_fee", value="100000", expected_version=0)
    assert row.value == "100000" and row.history.count() == 1


def test_governance_designation_requires_trusted_setup_and_audit():
    from django.core.management import call_command
    from django.core.management.base import CommandError
    manager = account("management")
    with pytest.raises(CommandError):
        call_command("designate_management_office", manager.email, "DIRECTOR", setup_actor=manager.email, reason="Initial setup")
    manager.is_superuser = True
    manager.save(update_fields=["is_superuser"])
    call_command("designate_management_office", manager.email, "DIRECTOR", setup_actor=manager.email, reason="Initial setup")
    manager.refresh_from_db()
    assert manager.management_position == "DIRECTOR"
    assert AdministrationHistory.objects.get().reason == "Initial setup"


def test_audit_failure_rolls_back_account_and_history():
    manager, buyer = account("management"), account("buyer")
    with patch("apps.administration.services.create_audit_log", side_effect=RuntimeError("audit")):
        with pytest.raises(RuntimeError):
            services.account_change(actor=manager, user_id=buyer.pk, version=1, reason="Policy", active=False)
    buyer.refresh_from_db()
    assert buyer.is_active and not AdministrationHistory.objects.exists()


def test_database_rejects_management_and_settings_history_rewrites():
    manager, buyer = account("management"), account("buyer")
    services.account_change(actor=manager, user_id=buyer.pk, version=1, reason="Policy", active=False)
    row = change_setting(actor=manager, key="free_check_daily_limit", value=4)
    for sql in ["DELETE FROM administration_administrationhistory", "UPDATE verification_settinghistory SET version=99"]:
        with pytest.raises(DatabaseError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(sql)


def test_management_cannot_overpost_governance_or_credentials():
    manager, buyer = account("management"), account("buyer")
    client = APIClient()
    client.force_authenticate(manager)
    path = f"/api/v1/management/accounts/{buyer.pk}/"
    assert client.post(path, {"version": 1, "reason": "Policy", "active": False, "management_position": "DIRECTOR"}, format="json").status_code == 400
    assert client.get(path).data["version"] == 1


def test_existing_locality_workflow_remains_authorized_management():
    from apps.localities.services import create_locality
    from apps.verification.tests.test_models_services import create_property
    manager, owner = account("management"), account("owner")
    prop = create_property(owner)
    row = create_locality(actor=manager, ward=prop.ward, name="Approved street", kind="street")
    assert row.approved
    with pytest.raises(PermissionDenied):
        create_locality(actor=owner, ward=prop.ward, name="Denied street", kind="street")


def test_listing_suspension_uses_existing_policy_and_records_reason():
    from apps.listings.tests.test_services import create_listing_for
    owner, manager = account("owner"), account("management")
    listing = create_listing_for(owner, status="ACTIVE")
    result = services.listing_change(actor=manager, listing_id=listing.listing_id, version=listing.updated_at.isoformat(), reason="Policy breach", action="suspend")
    assert result.status == "SUSPENDED"
    assert AdministrationHistory.objects.get().reason == "Policy breach"
    with pytest.raises(Conflict):
        services.listing_change(actor=manager, listing_id=listing.listing_id, version=listing.updated_at.isoformat(), reason="Reviewed", action="restore")


@pytest.mark.django_db(transaction=True)
def test_concurrent_settings_one_expected_version_wins():
    manager = account("management")
    def mutate():
        try:
            change_setting(actor=manager, key="free_check_daily_limit", value=4, expected_version=0)
            return "OK"
        except Conflict:
            return "STALE"
    assert sorted(concurrent(mutate)) == ["OK", "STALE"]
    assert VerificationSetting.objects.get().history.count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_account_changes_one_expected_version_wins():
    manager, buyer = account("management"), account("buyer")
    def mutate():
        try:
            services.account_change(actor=manager, user_id=buyer.pk, version=1, reason="Policy", active=False)
            return "OK"
        except Conflict:
            return "STALE"
    assert sorted(concurrent(mutate)) == ["OK", "STALE"]
    assert AdministrationHistory.objects.count() == 1
