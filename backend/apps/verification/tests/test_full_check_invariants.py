import pytest
from datetime import timedelta
from django.db import DatabaseError, connection, transaction
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError
from apps.audit.models import AuditLog
from apps.professionals.tests.test_professionals import storage, account
from apps.verification.models import VerificationNotice, VerificationJob
from apps.verification.services import get_effective_verification_level
from apps.verification import full_check_services as services
from .test_full_check import workflow, order, complete, under_review

pytestmark = pytest.mark.django_db


def test_raw_promotion_without_full_check_prerequisites_is_rejected(workflow):
    job = order(workflow)
    with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("UPDATE verification_verificationjob SET status='PASSED', completed_at=NOW(), expires_at=NOW()+INTERVAL '30 days', verifier_id=%s WHERE id=%s", [workflow[1].pk, job.pk])
    assert get_effective_verification_level(user=workflow[3], property_record=job.property) < 3


def test_order_replay_preserves_frozen_fee_after_quote_configuration_changes(workflow):
    token = services.quote()["quote"]
    values = {"actor": workflow[2], "listing_id": workflow[5].listing_id, "quote_token": token, "key": "original-order"}
    first = services.order_full_check(**values)
    from apps.verification.configuration import change_setting
    change_setting(actor=workflow[0], key="full_check_fee", value="200000")
    assert services.order_full_check(**values) == first
    from apps.payments.idempotency import Conflict
    with pytest.raises(Conflict):
        services.order_full_check(**{**values, "key": "different-order"})


def test_adverse_check_is_internal_blocks_existing_and_later_level_three(workflow):
    first = complete(workflow)
    adverse_workflow = (*workflow[:2], account("buyer"), *workflow[3:])
    adverse = complete(adverse_workflow, result="PROBLEM_FOUND", adverse=True)
    first.refresh_from_db()
    assert first.invalidated_at and first.result.result == "PASSED"
    assert get_effective_verification_level(user=workflow[3], property_record=first.property) < 3
    later_workflow = (*workflow[:2], account("buyer"), *workflow[3:])
    later = under_review(later_workflow)
    with pytest.raises(ValidationError):
        services.finalize_full_check(actor=workflow[1], job_id=later.pk, result="PASSED", risk_assessment="Cannot silently clear the prior issue")
    assert not later.reports.exists()
    client = APIClient()
    client.force_authenticate(workflow[1])
    response = client.get(f"/api/v1/full-checks/{later.pk}/")
    assert response.data["internal_property_flags"]["unresolved_adverse_full_check"] is True
    client.force_authenticate(later_workflow[2])
    assert "internal_property_flags" not in client.get(f"/api/v1/full-checks/{later.pk}/").data
    from apps.lister_identity.services import get_public_verification_summary
    assert "PROBLEM_FOUND" not in repr(get_public_verification_summary(user=workflow[3], property_record=first.property))


def test_private_payment_proof_and_tax_receipt_access_is_scoped(workflow):
    from .test_full_check import paid
    job = paid(workflow)
    proof = job.payment_proofs.get()
    url = f"/api/v1/full-checks/{job.pk}/payment-documents/{proof.media_id}/"
    client = APIClient()
    for actor in [workflow[3], workflow[1], account("buyer"), workflow[6].user]:
        client.force_authenticate(actor)
        assert client.get(url).status_code == 404
    for actor in [workflow[0], workflow[2]]:
        client.force_authenticate(actor)
        assert client.get(url).status_code == 200
        documents = client.get(f"/api/v1/full-checks/{job.pk}/proof/").data
        assert documents["proofs"][0]["document_id"] == str(proof.media_id)
        tax_url = f"/api/v1/full-checks/{job.pk}/payment-documents/{documents['tax_receipt']['document_id']}/"
        assert client.get(tax_url).status_code == 200


def test_declared_conflict_invalidates_previous_reliance_without_destroying_evidence(workflow):
    first = complete(workflow)
    later_workflow = (*workflow[:2], account("buyer"), *workflow[3:])
    from .test_full_check import started
    later = started(later_workflow)
    from apps.professionals.services import assign_professional
    task = later.tasks.get(kind="PROFESSIONAL")
    assign_professional(actor=workflow[1], task_id=task.pk, profile_id=workflow[6].pk)
    from apps.verification.relationships import declare_task_relationship
    declare_task_relationship(actor=workflow[6].user, task_id=task.pk, reason="Related to the Owner")
    first.refresh_from_db()
    assert first.invalidated_at and first.result.result == "PASSED" and first.reports.count() == 1
    assert get_effective_verification_level(user=workflow[3], property_record=first.property) < 3


def test_public_dates_and_stored_level_use_same_authoritative_result(workflow):
    job = complete(workflow)
    from apps.verification.models import VerificationLevelSnapshot
    from apps.lister_identity.services import get_public_verification_summary
    assert VerificationLevelSnapshot.objects.get(listing=workflow[5]).level == 3
    summary = get_public_verification_summary(user=workflow[3], property_record=job.property)
    assert summary["label"] == "Oweru Verified" and summary["completed_at"] == job.completed_at
    assert summary["expires_at"] == job.expires_at
    assert len(summary["checks"][0]["partners"]) == 2
    assert "risk_assessment" not in repr(summary)
    from apps.verification.deadlines import process_deadlines
    process_deadlines(at=job.expires_at + timedelta(seconds=1))
    assert VerificationLevelSnapshot.objects.get(listing=workflow[5]).level < 3


def test_material_title_change_invalidates_without_rewriting_passed_history(workflow):
    job = complete(workflow)
    from apps.properties.services import update_property_record
    update_property_record(actor=workflow[3], property_record=job.property, title_type="NONE")
    job.refresh_from_db()
    assert job.invalidated_at and job.status == "PASSED" and job.result.result == "PASSED"
    assert get_effective_verification_level(user=workflow[3], property_record=job.property) < 3


def test_order_context_and_final_evidence_media_are_database_locked(workflow):
    job = complete(workflow)
    report = job.reports.get()
    for sql, params in [("UPDATE verification_verificationjob SET fee=1 WHERE id=%s", [job.pk]), ("UPDATE media_media SET file_key='replaced' WHERE id=%s", [report.media_id]), ("DELETE FROM verification_verificationresult WHERE id=%s", [job.result.pk])]:
        with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(sql, params)


def test_refresh_versions_report_and_cannot_exceed_six_month_ceiling(workflow):
    job = complete(workflow)
    original = job.reports.get()
    original_expiry = job.expires_at
    refreshed = services.refresh_full_check(actor=workflow[1], job_id=job.pk, risk_assessment="New dated desk review")
    assert refreshed.reports.count() == 2
    assert refreshed.reports.order_by("-version").first().assessment_snapshot == "New dated desk review"
    assert refreshed.expires_at > original_expiry
    original.refresh_from_db()
    assert original.version == 1
    VerificationJob.objects.filter(pk=job.pk).update(refresh_limit_at=timezone.now() - timedelta(seconds=1))
    with pytest.raises(ValidationError):
        services.refresh_full_check(actor=workflow[1], job_id=job.pk, risk_assessment="Too late")


def test_whatsapp_outbox_is_staff_only_and_delivery_is_idempotently_audited(workflow):
    job = complete(workflow)
    manager, _, buyer, owner, _, _, profile = workflow
    client = APIClient()
    client.force_authenticate(buyer)
    assert client.get("/api/v1/management/verification-outbox/").status_code == 403
    client.force_authenticate(manager)
    with override_settings(PASSWORD_RESET_URL="https://example.test/password/reset"):
        response = client.get("/api/v1/management/verification-outbox/")
    assert response.status_code == 200
    login = next(row for row in response.data if row["purpose"] == "PROFESSIONAL_LOGIN")
    assert profile.user.email in login["message"] and "token=" in login["message"]
    assert not any(row["purpose"] == "FULL_CHECK_REPORT_READY" for row in response.data)
    ready = VerificationNotice.objects.get(job=job, purpose="FULL_CHECK_REPORT_READY")
    assert ready.recipient_id == buyer.pk and ready.channels == ["screen", "email"]
    notice = VerificationNotice.objects.get(pk=login["id"])
    url = f"/api/v1/management/verification-outbox/{notice.pk}/sent/"
    assert client.post(url, {}, format="json").status_code == 200
    assert client.post(url, {}, format="json").status_code == 200
    assert AuditLog.objects.filter(action="verification.notice_sent", entity_id=notice.pk).count() == 1
    client.force_authenticate(owner)
    assert client.post(url, {}, format="json").status_code == 403
