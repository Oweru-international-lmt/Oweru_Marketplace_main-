from datetime import timedelta
from unittest.mock import patch
import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.professionals.tests.test_professionals import account, storage, pdf
from apps.payments.tests.test_concurrency import concurrent
from apps.payments.idempotency import Conflict
from apps.payments.models import PayoutBlock
from apps.audit.models import AuditLog
from apps.complaints.models import Complaint, ComplaintHistory
from apps.complaints import services

pytestmark = pytest.mark.django_db


def inputs(**changes):
    return {"name": "Complainant", "phone": "+255712345678", "complainant_role": "buyer", "category": "PAYMENT", "description": "Please investigate", **changes}


def move(manager, row, status, outcome=""):
    return services.transition(actor=manager, complaint_id=row.pk, status=status, version=row.version, reason="Investigation reason", outcome=outcome)


def test_anonymous_intake_number_status_and_private_evidence():
    client = APIClient()
    response = client.post("/api/v1/complaints/", inputs(), format="json")
    assert response.status_code == 201 and response.data["reference"].startswith("CMP-")
    row = Complaint.objects.get()
    assert client.get(f"/api/v1/complaints/{row.pk}/status/").status_code == 403
    status = client.get(f"/api/v1/complaints/{row.pk}/status/", {"token": services.token_for(row)})
    assert status.status_code == 200
    assert not {"phone", "name", "description", "evidence", "handler"} & status.data.keys()
    assert client.get(f"/api/v1/management/complaints/{row.pk}/").status_code == 401


@pytest.mark.parametrize("category,route", [("FAKE_LISTING", "HEAD_OPERATIONS"), ("WRONG_LISTING", "HEAD_OPERATIONS"), ("OTHER", "HEAD_OPERATIONS"), ("CONDUCT", "MANAGEMENT"), ("PAYMENT", "MANAGEMENT"), ("PAYOUT", "MANAGEMENT"), ("PRIVACY", "MANAGEMENT"), ("VERIFICATION", "VERIFIER")])
def test_category_routes(category, route):
    assert services.lodge(values=inputs(category=category)).route == route


def test_staff_intake_channel_acknowledgement():
    staff = account("marketer")
    row = services.lodge(values=inputs(), source="WHATSAPP", actor=staff)
    assert row.notices.get().channels == ["screen", "outbox"]
    assert row.created_by_id == staff.pk
    email = services.lodge(values=inputs(email="person@example.test"), source="EMAIL", actor=staff)
    assert email.notices.get().channels == ["screen", "email"]
    with pytest.raises(PermissionDenied):
        services.lodge(values=inputs(), source="WHATSAPP", actor=account("buyer"))


def test_transition_reason_resolution_history_and_version():
    manager = account("management")
    row = services.lodge(values=inputs(), evidence=[pdf()])
    row = move(manager, row, "IN_REVIEW")
    with pytest.raises(ValidationError):
        move(manager, row, "CLOSED")
    with pytest.raises(ValidationError):
        move(manager, row, "RESOLVED")
    row = move(manager, row, "WAITING_INFORMATION")
    response = services.add_response(complaint_id=row.pk, token=services.token_for(row), text="Additional facts", evidence=[pdf()])
    assert response.from_complainant and row.evidence.count() == 2
    row = move(manager, row, "RESOLVED", "Resolution reached")
    assert row.history.count() == 4 and row.outcome == "Resolution reached"
    with pytest.raises(Conflict):
        services.transition(actor=manager, complaint_id=row.pk, status="CLOSED", version=1, reason="stale")
    with pytest.raises(ValidationError):
        row.history.all().delete()


def test_director_only_final_review_and_one_request():
    manager, director = account("management"), account("management")
    director.management_position = "DIRECTOR"
    director.save(update_fields=["management_position"])
    row = services.lodge(values=inputs())
    row = move(manager, row, "IN_REVIEW")
    row = move(manager, row, "RESOLVED", "Outcome")
    row = services.request_final_review(complaint_id=row.pk, token=services.token_for(row), reason="Disagree")
    with pytest.raises(PermissionDenied):
        move(manager, row, "CLOSED", "Rejected")
    with pytest.raises(ValidationError):
        services.request_final_review(complaint_id=row.pk, token=services.token_for(row), reason="Again")
    row = move(director, row, "CLOSED", "Final outcome")
    assert row.status == "CLOSED"


def test_final_review_window_and_capability_binding():
    manager = account("management")
    row = services.lodge(values=inputs())
    other = services.lodge(values=inputs())
    with pytest.raises(PermissionDenied):
        services.public_access(other.pk, services.token_for(row))
    row = move(manager, row, "IN_REVIEW")
    row = move(manager, row, "RESOLVED", "Outcome")
    with patch("apps.complaints.services.timezone.now", return_value=row.resolved_at + timedelta(days=15)):
        with pytest.raises(ValidationError):
            services.request_final_review(complaint_id=row.pk, token=services.token_for(row), reason="Late")


def test_assigned_verifier_scope_escalation():
    manager, verifier, other = account("management"), account("verifier"), account("verifier")
    row = services.lodge(values=inputs(category="VERIFICATION"))
    row = services.assign(actor=manager, complaint_id=row.pk, handler=verifier, version=row.version)
    assert services.require_handler(verifier, row).pk == verifier.pk
    with pytest.raises(PermissionDenied):
        services.require_handler(other, row)
    row = services.assign(actor=verifier, complaint_id=row.pk, handler=manager, version=row.version, escalate=True)
    with pytest.raises(PermissionDenied):
        services.require_handler(verifier, row)
    with pytest.raises(PermissionDenied):
        services.require_handler(verifier, services.lodge(values=inputs(category="PRIVACY")))


def test_overdue_targets_working_days():
    now = timezone.now()
    payment = services.lodge(values=inputs())
    other = services.lodge(values=inputs(category="CONDUCT"))
    assert payment.resolution_due_at < other.resolution_due_at
    assert payment.acknowledgement_due_at > now


def test_evidence_api_cannot_be_read_by_unassigned_verifier():
    manager, verifier = account("management"), account("verifier")
    row = services.lodge(values=inputs(), evidence=[pdf()])
    client = APIClient()
    client.force_authenticate(verifier)
    path = f"/api/v1/management/complaints/{row.pk}/evidence/{row.evidence.get().pk}/"
    assert client.get(path).status_code == 403
    client.force_authenticate(manager)
    response = client.get(path)
    assert response.status_code == 200 and "file_key" not in str(response.data)


def test_atomic_rollback_preserves_no_complaint_or_evidence():
    from apps.media.storage import get_private_media_storage
    with patch("apps.complaints.services.create_audit_log", side_effect=RuntimeError("audit")):
        with pytest.raises(RuntimeError):
            services.lodge(values=inputs(), evidence=[pdf()])
    assert not Complaint.objects.exists() and not get_private_media_storage().objects


def test_database_guards_reject_history_and_intake_edits():
    from django.db import connection, transaction, DatabaseError
    row = services.lodge(values=inputs())
    for sql in ["UPDATE complaints_complaint SET description='changed' WHERE id=%s", "DELETE FROM complaints_complainthistory WHERE complaint_id=%s"]:
        with pytest.raises(DatabaseError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(sql, [row.pk])


def test_complaint_evidence_media_cannot_be_repointed_or_deleted():
    from django.db import connection, transaction, DatabaseError
    row = services.lodge(values=inputs(), evidence=[pdf()])
    media_id = row.evidence.get().media_id
    for sql in ["UPDATE media_media SET file_key='replacement.pdf' WHERE id=%s", "DELETE FROM media_media WHERE id=%s"]:
        with pytest.raises(DatabaseError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(sql, [media_id])


def test_closed_complaint_can_request_final_review_within_window():
    manager = account("management")
    row = services.lodge(values=inputs())
    row = move(manager, row, "IN_REVIEW")
    row = move(manager, row, "RESOLVED", "Outcome")
    row = move(manager, row, "CLOSED")
    assert services.request_final_review(complaint_id=row.pk, token=services.token_for(row), reason="Disagree").status == "UNDER_FINAL_REVIEW"


def test_unknown_api_action_and_client_controlled_intake_fields_rejected():
    manager = account("management")
    row = services.lodge(values=inputs())
    client = APIClient()
    client.force_authenticate(manager)
    assert client.post(f"/api/v1/management/complaints/{row.pk}/unknown/", {}, format="json").status_code == 400
    assert client.post(f"/api/v1/management/complaints/{row.pk}/transition/", {"status": "IN_REVIEW", "version": 1, "reason": "Review", "handler_id": str(manager.pk)}, format="json").status_code == 400


def test_head_of_operations_routing_is_enforced():
    manager = account("management")
    row = services.lodge(values=inputs(category="FAKE_LISTING"))
    with pytest.raises(PermissionDenied):
        services.require_handler(manager, row)
    manager.management_position = "HEAD_OPERATIONS"
    manager.save(update_fields=["management_position"])
    assert services.require_handler(manager, row).pk == manager.pk


@pytest.mark.django_db(transaction=True)
def test_concurrent_transitions_only_one_version_wins():
    manager = account("management")
    row = services.lodge(values=inputs())
    def mutate():
        try:
            services.transition(actor=manager, complaint_id=row.pk, status="IN_REVIEW", version=1, reason="review")
            return "OK"
        except Conflict:
            return "STALE"
    assert sorted(concurrent(mutate)) == ["OK", "STALE"]
    assert ComplaintHistory.objects.filter(complaint=row).count() == 2
