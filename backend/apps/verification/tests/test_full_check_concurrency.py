import pytest
from django.db import close_old_connections
from rest_framework.exceptions import ValidationError, PermissionDenied
from apps.accounts.models import User
from apps.payments.idempotency import Conflict
from apps.payments.tests.test_concurrency import concurrent
from apps.professionals.services import assign_professional, decide_task
from apps.professionals.tests.test_professionals import storage, pdf
from .test_full_check import workflow, order, paid, started, under_review, official_answers, valid_capture
from apps.verification import full_check_services as services
from apps.verification.task_services import submit_task
from apps.verification.models import VerificationJob, FullCheckReceipt, TaskSubmission, VerificationResult, VerificationReport, VerificationTask

pytestmark = pytest.mark.django_db(transaction=True)


def test_same_key_orders_concurrently_create_one_job(workflow):
    _, _, buyer, _, _, listing, _ = workflow
    quote = services.quote()["quote"]
    results = concurrent(lambda: services.order_full_check(actor=User.objects.get(pk=buyer.pk), listing_id=listing.listing_id, quote_token=quote, key="concurrent-order"))
    assert results[0] == results[1]
    assert VerificationJob.objects.count() == 1


def test_concurrent_payment_confirmation_creates_one_receipt(workflow):
    job = order(workflow)
    manager = workflow[0]
    results = concurrent(lambda: services.confirm_full_check_payment(actor=User.objects.get(pk=manager.pk), job_id=job.pk, amount=job.fee, reference=job.payment_reference, bank_reference="BANK", tax_receipt_number="CONCURRENT-TAX", tax_receipt=pdf(), key="same"))
    assert results[0] == results[1]
    assert FullCheckReceipt.objects.count() == 1


def test_concurrent_professional_decision_only_accepts_once(workflow):
    job = started(workflow)
    profile = workflow[6]
    task = job.tasks.get(kind="PROFESSIONAL")
    assign_professional(actor=workflow[1], task_id=task.pk, profile_id=profile.pk)
    def decide():
        try:
            decide_task(actor=User.objects.get(pk=profile.user_id), task_id=task.pk, decision="ACCEPT")
            return "ACCEPTED"
        except ValidationError:
            return "REJECTED"
    assert sorted(concurrent(decide)) == ["ACCEPTED", "REJECTED"]
    assert task.assignment_history.filter(action="ACCEPT").count() == 1


def test_concurrent_official_submission_first_complete_wins(workflow):
    job = started(workflow)
    submit_task(actor=workflow[3], task_id=job.tasks.get(kind="SITE_CAPTURE").pk, findings={}, device="phone", capture=valid_capture(workflow[3], job.property))
    task = job.tasks.get(kind="LOCAL_OFFICE")
    official = workflow[4]
    def submit():
        try:
            submit_task(actor=User.objects.get(pk=official.pk), task_id=task.pk, findings=official_answers(), device="phone", report=pdf(), signed_and_stamped=True)
            return "SUBMITTED"
        except ValidationError:
            return "REJECTED"
    assert sorted(concurrent(submit)) == ["REJECTED", "SUBMITTED"]
    assert TaskSubmission.objects.filter(task=task).count() == 1


def test_concurrent_final_review_generates_one_result_report_and_promotion(workflow):
    job = under_review(workflow)
    verifier = workflow[1]
    def finish():
        try:
            services.finalize_full_check(actor=User.objects.get(pk=verifier.pk), job_id=job.pk, result="PASSED", risk_assessment="Reviewed all evidence")
            return "PASSED"
        except ValidationError:
            return "REJECTED"
    assert sorted(concurrent(finish)) == ["PASSED", "REJECTED"]
    assert VerificationResult.objects.filter(job=job).count() == 1
    assert VerificationReport.objects.filter(job=job).count() == 1
