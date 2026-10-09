from datetime import timedelta
from unittest.mock import patch
import pytest
from django.test import override_settings
from django.utils import timezone
from django.db import transaction
from rest_framework.test import APIClient
from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.professionals.tests.test_professionals import account, storage
from apps.payments.tests.test_concurrency import concurrent
from apps.payments.idempotency import Conflict
from apps.roles.services import grant_permission, revoke_permission
from apps.notifications.models import Notification, DeliveryAttempt
from apps.notifications import services
from apps.complaints.services import lodge
from apps.complaints.tests.test_complaints import inputs
from apps.free_checks.services import submit
from apps.free_checks.tests.test_free_checks import inputs as free_inputs

pytestmark = pytest.mark.django_db


class Adapter:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def deliver(self, row):
        self.calls.append(row.pk)
        if self.fail:
            raise RuntimeError("credentials must never be recorded")


def test_four_channels_and_forbidden_sms():
    user = account("buyer")
    rows = services.emit(event_key="event", purpose="PAYMENT_INSTRUCTIONS", channels=Notification.CHANNELS, recipient=user)
    assert len(rows) == 4
    assert len(services.emit(event_key="event", purpose="PAYMENT_INSTRUCTIONS", channels=Notification.CHANNELS, recipient=user)) == 4
    assert Notification.objects.count() == 4
    with pytest.raises(ValidationError):
        services.emit(event_key="sms", purpose="PHONE", channels=["sms"], recipient=user)


def test_no_messages_escape_rolled_back_transaction():
    user = account("buyer")
    with pytest.raises(RuntimeError), transaction.atomic():
        services.emit(event_key="rolled", purpose="LEAD_CREATED", channels=["screen", "email"], recipient=user)
        raise RuntimeError()
    assert not Notification.objects.exists()


def test_worker_never_automatically_sends_whatsapp():
    user = account("buyer")
    services.emit(event_key="event", purpose="LEAD_CREATED", channels=Notification.CHANNELS, recipient=user)
    adapter = Adapter()
    assert services.process_pending(adapter=adapter) == 1
    assert len(adapter.calls) == 1
    assert Notification.objects.get(channel="outbox").status == "WAITING"
    assert Notification.objects.get(channel="self_service").status == "WAITING"


def test_failed_email_retry_success_and_redacted_failure_log():
    user = account("buyer")
    row = services.emit(event_key="retry", purpose="LEAD_CREATED", channels=["email"], recipient=user)[0]
    failed = services.deliver_email(row.pk, Adapter(fail=True))
    assert failed.status == "FAILED" and failed.attempts == 1
    assert failed.delivery_attempts.get().error_type == "RuntimeError"
    adapter = Adapter()
    services.deliver_email(row.pk, adapter)
    assert not adapter.calls
    with patch("apps.notifications.services.timezone.now", return_value=failed.retry_at + timedelta(seconds=1)):
        delivered = services.deliver_email(row.pk, adapter)
    assert delivered.status == "SENT" and delivered.attempts == 2
    services.deliver_email(row.pk, adapter)
    assert len(adapter.calls) == 1 and DeliveryAttempt.objects.count() == 2


def test_inbox_object_isolation_and_inactive_recipient():
    first, second = account("buyer"), account("buyer")
    row = services.emit(event_key="own", purpose="LEAD_CREATED", channels=["screen"], recipient=first)[0]
    client = APIClient()
    client.force_authenticate(second)
    assert client.get("/api/v1/notifications/").data == []
    assert client.post(f"/api/v1/notifications/{row.pk}/read/", {}, format="json").status_code == 404
    client.force_authenticate(first)
    assert client.post(f"/api/v1/notifications/{row.pk}/read/", {}, format="json").status_code == 200


def test_manual_outbox_granted_staff_and_revocation():
    manager, verifier, buyer = account("management"), account("verifier"), account("buyer")
    row = services.emit(event_key="manual", purpose="TASK_ASSIGNED", channels=["outbox"], recipient=buyer)[0]
    with pytest.raises(PermissionDenied):
        services.mark_sent(actor=verifier, notification_id=row.pk)
    grant_permission(actor=manager, role_code="verifier", permission_code="outbox.send")
    sent = services.mark_sent(actor=verifier, notification_id=row.pk)
    assert sent.status == "SENT" and sent.sent_by_id == verifier.pk
    revoke_permission(actor=manager, role_code="verifier", permission_code="outbox.send")
    with pytest.raises(PermissionDenied):
        services.mark_sent(actor=verifier, notification_id=row.pk)


def test_templates_bilingual_versioned_and_safe_placeholders():
    manager = account("management")
    services.change_template(actor=manager, key="LEAD_CREATED", en="Hello {reference} {link}", sw="Habari {reference} {link}", version=0)
    assert services.render("LEAD_CREATED", "sw", {"reference": "123", "link": "link"}) == ("Habari 123 link", 1)
    with pytest.raises(Conflict):
        services.change_template(actor=manager, key="LEAD_CREATED", en="x {link}", sw="y {link}", version=0)
    with pytest.raises(ValidationError):
        services.change_template(actor=manager, key="LEAD_CREATED", en="{link.__class__}", sw="{link}", version=1)
    with pytest.raises(PermissionDenied):
        services.change_template(actor=account("marketer"), key="LEAD_CREATED", en="x {link}", sw="y {link}", version=1)


def test_complaint_and_free_check_intents_reach_correct_channels():
    manager = account("management")
    row = lodge(values=inputs(email="complainant@example.test"), source="WHATSAPP", actor=manager)
    assert set(Notification.objects.filter(purpose="COMPLAINT_NUMBER").values_list("channel", flat=True)) == {"screen", "outbox"}
    free = submit(values=free_inputs(email="free@example.test"), key="email")
    assert set(Notification.objects.filter(purpose="FREE_CHECK_REPORT").values_list("channel", flat=True)) == {"screen", "email", "self_service"}
    assert not Notification.objects.filter(purpose="FREE_CHECK_REPORT", channel="outbox").exists()


def test_smtp_adapter_with_django_test_backend():
    from django.core import mail
    user = account("buyer")
    row = services.emit(event_key="smtp", purpose="LEAD_CREATED", channels=["email"], recipient=user)[0]
    services.deliver_email(row.pk)
    assert len(mail.outbox) == 1 and mail.outbox[0].to == [user.email]
    assert mail.outbox[0].extra_headers["Message-ID"] == f"<oweru-{row.pk}@marketplace>"


def test_outbox_api_history_no_sender_control():
    manager, recipient = account("management"), account("buyer")
    row = services.emit(event_key="manual-api", purpose="TASK_ASSIGNED", channels=["outbox"], recipient=recipient)[0]
    client = APIClient()
    client.force_authenticate(manager)
    assert client.get("/api/v1/management/notifications/outbox/").status_code == 200
    path = f"/api/v1/management/notifications/outbox/{row.pk}/sent/"
    assert client.post(path, {"sent_by": str(recipient.pk)}, format="json").status_code == 400
    assert client.post(path, {}, format="json").status_code == 200
    assert len(client.get("/api/v1/management/notifications/outbox/", {"history": "1"}).data) == 1


def test_working_hour_highlight_skips_weekends():
    import datetime
    start = timezone.make_aware(datetime.datetime(2026, 10, 9, 23))
    end = timezone.make_aware(datetime.datetime(2026, 10, 12, 1))
    assert services.working_hours(start, end) == 2


def test_reconciliation_is_idempotent_and_performs_no_delivery():
    from django.core.management import call_command
    manager = account("management")
    lodge(values=inputs(), source="WHATSAPP", actor=manager)
    before = Notification.objects.count()
    call_command("reconcile_notification_intents")
    call_command("reconcile_notification_intents")
    assert Notification.objects.count() == before
    assert not DeliveryAttempt.objects.exists()


def test_email_expired_or_inactive_recipient_is_cancelled():
    user = account("buyer")
    row = services.emit(event_key="expired", purpose="LEAD_CREATED", channels=["email"], recipient=user, expires_at=timezone.now() - timedelta(seconds=1))[0]
    adapter = Adapter()
    assert services.deliver_email(row.pk, adapter).status == "CANCELLED"
    assert not adapter.calls


def test_single_message_sent_is_idempotently_audited():
    from apps.audit.models import AuditLog
    manager, buyer = account("management"), account("buyer")
    row = services.emit(event_key="manual-repeat", purpose="TASK_ASSIGNED", channels=["outbox"], recipient=buyer)[0]
    services.mark_sent(actor=manager, notification_id=row.pk)
    services.mark_sent(actor=manager, notification_id=row.pk)
    assert AuditLog.objects.filter(action="notification.outbox_sent", entity_id=str(row.pk)).count() == 1


def test_confirmation_sent_history_preserves_message_after_consumption():
    from apps.payments.confirmations import queue_identity_phone_confirmation
    from apps.payments.models import ConfirmationDelivery
    manager, owner = account("management"), account("owner")
    delivery = queue_identity_phone_confirmation(owner)
    row = Notification.objects.get(source_id=delivery["delivery_id"])
    with override_settings(OWNER_CONFIRMATION_URL="https://marketplace.example.test/confirm"):
        preview = services.outbox_payload(row, None)
        assert owner.phone in preview["message"] and "token=" in preview["message"]
        services.mark_sent(actor=manager, notification_id=row.pk)
    ConfirmationDelivery.objects.filter(pk=delivery["delivery_id"]).update(consumed_at=timezone.now(), delivery_token="")
    row.refresh_from_db()
    history = services.outbox_payload(row, None)
    assert history["status"] == "SENT" and history["message"] == preview["message"]


def test_legacy_location_expiry_reminders_are_idempotent():
    from apps.notifications.tasks import verification_expiry_reminders
    from apps.listings.tests.test_services import create_listing_for
    from apps.verification.models import PropertyVerification
    owner, manager = account("owner"), account("management")
    listing = create_listing_for(owner)
    now = timezone.now()
    PropertyVerification.objects.create(property=listing.property, kind="FIELD", status="APPROVED", submitted_by=owner, reviewed_by=manager, submitted_at=now, reviewed_at=now, expires_at=now + timedelta(days=29))
    verification_expiry_reminders()
    verification_expiry_reminders()
    assert Notification.objects.filter(purpose="VERIFICATION_EXPIRING", recipient=owner).count() == 2


@pytest.mark.django_db(transaction=True)
def test_two_workers_submit_email_once():
    user = account("buyer")
    row = services.emit(event_key="concurrent", purpose="LEAD_CREATED", channels=["email"], recipient=user)[0]
    adapter = Adapter()
    concurrent(lambda: services.deliver_email(row.pk, adapter))
    assert len(adapter.calls) == 1 and DeliveryAttempt.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_manual_send_records_one_sender_and_audit():
    from apps.audit.models import AuditLog
    manager, buyer = account("management"), account("buyer")
    row = services.emit(event_key="concurrent-manual", purpose="TASK_ASSIGNED", channels=["outbox"], recipient=buyer)[0]
    concurrent(lambda: services.mark_sent(actor=manager, notification_id=row.pk))
    row.refresh_from_db()
    assert row.sent_by_id == manager.pk
    assert AuditLog.objects.filter(action="notification.outbox_sent", entity_id=str(row.pk)).count() == 1
