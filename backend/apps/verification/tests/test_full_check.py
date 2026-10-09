from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
import uuid
import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient
from apps.audit.models import AuditLog
from apps.listings.tests.test_services import create_listing_for
from apps.local_officials.services import create_local_official_profile
from apps.local_officials.full_check import assign_locality
from apps.media.storage import get_private_media_storage
from apps.payments.models import BankAccount, ConfirmationDelivery, OwnerContact
from apps.payments.confirmations import mark_sent
from apps.payments.idempotency import Conflict
from apps.professionals.services import register_professional, assign_professional, decide_task
from apps.professionals.tests.test_professionals import account, pdf, storage
from apps.site_capture.services import create_site_capture, record_corner, submit_site_capture
from apps.verification.configuration import change_setting
from apps.verification.models import VerificationJob, VerificationTask, VerificationResult, VerificationReport, FullCheckReceipt, TaskSubmission
from apps.verification import full_check_services as services
from apps.verification.task_services import submit_task
from apps.verification.services import get_effective_verification_level
from apps.verification.deadlines import process_deadlines

pytestmark = pytest.mark.django_db


@pytest.fixture
def workflow():
    manager, verifier, buyer, owner, official = [account(role) for role in ["management", "verifier", "buyer", "owner", "local_official"]]
    manager.management_position = "DIRECTOR"
    manager.save(update_fields=["management_position"])
    listing = create_listing_for(owner, lister_kind="OWNER", status="ACTIVE")
    listing.property.title_type = "REGISTERED_TITLE"
    listing.property.save(update_fields=["title_type"])
    change_setting(actor=manager, key="full_check_fee", value="100000")
    BankAccount.objects.create(is_oweru=True, bank_name="Bank", account_name="Oweru", account_number="12345", branch="Dar")
    profile = create_local_official_profile(actor=manager, user=official, official_number=uuid.uuid4().hex)
    assign_locality(actor=manager, official=profile, locality=listing.property.locality)
    professional_user = account("professional")
    professional = register_professional(actor=manager, professional_type="PLANNER", registration_number=uuid.uuid4().hex, national_id_number="PRIVATE-NATIONAL-ID", districts=[listing.property.district], user=professional_user)
    return manager, verifier, buyer, owner, official, listing, professional


def order(workflow, key="order"):
    _, _, buyer, _, _, listing, _ = workflow
    response = services.order_full_check(actor=buyer, listing_id=listing.listing_id, quote_token=services.quote()["quote"], key=key)
    return VerificationJob.objects.get(pk=response["job_id"])


def paid(workflow):
    manager, verifier, buyer, owner, official, listing, professional = workflow
    job = order(workflow)
    services.submit_payment_proof(actor=buyer, job_id=job.pk, upload=pdf(), key="proof")
    services.confirm_full_check_payment(actor=manager, job_id=job.pk, amount=job.fee, reference=job.payment_reference, bank_reference="BANK-FULL-CHECK", tax_receipt_number=uuid.uuid4().hex, tax_receipt=pdf(), key="confirm")
    services.assign_verifier(actor=manager, job_id=job.pk, verifier=verifier)
    job.refresh_from_db()
    return job


def started(workflow):
    job = paid(workflow)
    _, verifier, _, owner, _, _, _ = workflow
    services.owner_consent(actor=owner, job_id=job.pk, decision="CONFIRM")
    services.start_tasks(actor=verifier, job_id=job.pk, professional_types=["PLANNER"])
    job.refresh_from_db()
    return job


def valid_capture(owner, prop):
    capture = create_site_capture(actor=owner, property_record=prop, observed_point=prop.pin)
    lon, lat = prop.pin.x, prop.pin.y
    for x, y in [(lon, lat), (lon + 0.0003, lat), (lon + 0.0003, lat + 0.0003), (lon, lat + 0.0003)]:
        record_corner(actor=owner, site_capture=capture, point=Point(x, y, srid=4326), accuracy_m=5, observed_at=timezone.now(), device="browser-phone")
    return submit_site_capture(actor=owner, site_capture=capture)


def official_answers(adverse=False):
    values = {"1": "YES", "2": "YES", "3": "NO", "4": "NO", "5": "YES"}
    if adverse:
        values["4"] = "YES"
    return {key: {"answer": value, "comment": "Dispute recorded" if adverse and key == "4" else "Office records checked"} for key, value in values.items()}


def under_review(workflow, *, omit=None, adverse=False):
    manager, verifier, buyer, owner, official, listing, professional = workflow
    job = started(workflow)
    capture = valid_capture(owner, job.property)
    site = job.tasks.get(kind="SITE_CAPTURE")
    if omit != "SITE_CAPTURE":
        submit_task(actor=owner, task_id=site.pk, findings={}, device="browser-phone", capture=capture)
    local = job.tasks.get(kind="LOCAL_OFFICE")
    if omit not in {"SITE_CAPTURE", "LOCAL_OFFICE"}:
        submit_task(actor=official, task_id=local.pk, findings=official_answers(adverse), device="official-phone", report=pdf(), signed_and_stamped=True)
    professional_task = job.tasks.get(kind="PROFESSIONAL")
    assign_professional(actor=verifier, task_id=professional_task.pk, profile_id=professional.pk)
    decide_task(actor=professional.user, task_id=professional_task.pk, decision="ACCEPT")
    if omit != "PROFESSIONAL":
        submit_task(actor=professional.user, task_id=professional_task.pk, findings={"layout": "Reviewed", "development_restrictions": "Recorded", "planning_context": "Reviewed"}, device="professional-phone", report=pdf())
    registry = job.tasks.get(kind="REGISTRY")
    if omit != "REGISTRY":
        submit_task(actor=verifier, task_id=registry.pk, findings={"search_result": "Registered ownership checked", "reference": "REGISTRY-TEST"}, device="staff-browser", report=pdf())
    job.refresh_from_db()
    return job


def complete(workflow, *, result="PASSED", adverse=False):
    job = under_review(workflow, adverse=adverse)
    verifier = workflow[1]
    services.finalize_full_check(actor=verifier, job_id=job.pk, result=result, risk_assessment="All required evidence reviewed; risk assessment recorded.", not_checked=["Satellite imagery unavailable"])
    job.refresh_from_db()
    return job


def test_postgresql_postgis_end_to_end_full_check_to_level_three(workflow):
    manager, verifier, buyer, owner, official, listing, professional = workflow
    job = complete(workflow)
    assert job.status == "PASSED"
    assert job.payment_receipt.amount == job.fee
    assert job.consent.decision == "CONFIRM"
    assert job.tasks.filter(status="SUBMITTED").count() == 4
    assert job.result.verifier_id == verifier.pk
    assert job.reports.count() == 1
    report = job.reports.get()
    content = get_private_media_storage().objects[report.media.file_key]["bytes"]
    assert content.startswith(b"%PDF-") and b"%%EOF" in content[-2048:]
    assert get_effective_verification_level(user=owner, property_record=listing.property) == 3
    from apps.listings.public_search import get_public_listing_search_queryset
    target = get_public_listing_search_queryset({"min_verification_level": "3"}).get(pk=listing.pk)
    assert target.effective_verification_level == 3
    assert job.history.values_list("status", flat=True).count() >= 5
    for action in ["full_check.ordered", "full_check.payment_confirmed", "full_check.owner_consent", "full_check.final_result", "full_check.report_generated"]:
        assert AuditLog.objects.filter(action=action).exists()
    assert job.tasks.get(kind="LOCAL_OFFICE").submissions.get().author_id == official.pk
    assert job.tasks.get(kind="PROFESSIONAL").submissions.get().registration_number == professional.registration_number


@pytest.mark.parametrize("omit", ["SITE_CAPTURE", "LOCAL_OFFICE", "PROFESSIONAL", "REGISTRY"])
def test_skipping_any_mandatory_task_prevents_completion(workflow, omit):
    job = under_review(workflow, omit=omit)
    with pytest.raises(ValidationError):
        services.finalize_full_check(actor=workflow[1], job_id=job.pk, result="PASSED", risk_assessment="Cannot skip prerequisites")
    assert not job.reports.exists()
    assert get_effective_verification_level(user=workflow[3], property_record=job.property) != 3


def test_order_is_buyer_only_and_replay_is_idempotent(workflow):
    manager, _, buyer, owner, _, listing, _ = workflow
    with pytest.raises(PermissionDenied):
        services.order_full_check(actor=owner, listing_id=listing.listing_id, quote_token=services.quote()["quote"], key="owner")
    first = order(workflow)
    second = order(workflow)
    assert first.pk == second.pk
    assert VerificationJob.objects.count() == 1
    with pytest.raises(Conflict):
        order(workflow, key="another-order")
    with pytest.raises(ValidationError):
        services.order_full_check(actor=buyer, listing_id=listing.listing_id, quote_token="tampered", key="bad")


def test_fee_quote_changes_require_buyer_review(workflow):
    old = services.quote()["quote"]
    change_setting(actor=workflow[0], key="full_check_fee", value="120000")
    with pytest.raises(Conflict):
        services.order_full_check(actor=workflow[2], listing_id=workflow[5].listing_id, quote_token=old, key="old-quote")


@pytest.mark.parametrize("phase", ["unpaid", "paid_without_consent", "consent_declined"])
def test_verification_cannot_start_before_paid_consent(workflow, phase):
    manager, verifier, _, owner, _, _, _ = workflow
    job = order(workflow) if phase == "unpaid" else paid(workflow)
    if phase == "unpaid":
        services.assign_verifier(actor=manager, job_id=job.pk, verifier=verifier)
    if phase == "consent_declined":
        services.owner_consent(actor=owner, job_id=job.pk, decision="DECLINE")
    with pytest.raises(ValidationError):
        services.start_tasks(actor=verifier, job_id=job.pk)
    assert not job.tasks.exists()


def test_owner_consent_cannot_be_given_by_another_user(workflow):
    job = paid(workflow)
    for attacker in [workflow[2], workflow[0], account("agent")]:
        with pytest.raises(PermissionDenied):
            services.owner_consent(actor=attacker, job_id=job.pk, decision="CONFIRM")
    assert not hasattr(job, "consent")


def test_payment_confirmation_idempotency_and_amount_reference_validation(workflow):
    manager, _, buyer, _, _, _, _ = workflow
    job = order(workflow)
    args = dict(actor=manager, job_id=job.pk, amount=job.fee, reference=job.payment_reference, bank_reference="BANK", tax_receipt_number="TAX-TEST", key="same")
    with pytest.raises(ValidationError):
        services.confirm_full_check_payment(**{**args, "amount": 1}, tax_receipt=pdf())
    with pytest.raises(ValidationError):
        services.confirm_full_check_payment(**{**args, "reference": uuid.uuid4()}, tax_receipt=pdf())
    first = services.confirm_full_check_payment(**args, tax_receipt=pdf())
    second = services.confirm_full_check_payment(**args, tax_receipt=pdf())
    assert first == second
    assert FullCheckReceipt.objects.filter(job=job).count() == 1
    assert AuditLog.objects.filter(action="full_check.payment_confirmed", entity_id=str(job.pk)).count() == 1
    with pytest.raises(Conflict):
        services.confirm_full_check_payment(**{**args, "bank_reference": "OTHER"}, tax_receipt=pdf())
    with pytest.raises(PermissionDenied):
        services.confirm_full_check_payment(**{**args, "actor": buyer}, tax_receipt=pdf())


def test_payment_proof_replay_is_authorized_and_private(workflow):
    job = order(workflow)
    buyer = workflow[2]
    first = services.submit_payment_proof(actor=buyer, job_id=job.pk, upload=pdf(), key="proof")
    assert first == services.submit_payment_proof(actor=buyer, job_id=job.pk, upload=pdf(), key="proof")
    with pytest.raises(PermissionDenied):
        services.submit_payment_proof(actor=account("buyer"), job_id=job.pk, upload=pdf(), key="proof")
    buyer.user_roles.update(is_active=False)
    with pytest.raises(PermissionDenied):
        services.submit_payment_proof(actor=buyer, job_id=job.pk, upload=pdf(), key="proof")


def test_adverse_answers_cannot_be_silently_passed(workflow):
    job = under_review(workflow, adverse=True)
    with pytest.raises(ValidationError):
        services.finalize_full_check(actor=workflow[1], job_id=job.pk, result="PASSED", risk_assessment="Ignore dispute")
    services.finalize_full_check(actor=workflow[1], job_id=job.pk, result="PROBLEM_FOUND", risk_assessment="Dispute recorded")
    assert get_effective_verification_level(user=workflow[3], property_record=job.property) != 3


def test_buyer_private_report_and_result_are_not_available_to_lister_or_other_buyer(workflow):
    job = complete(workflow, result="PROBLEM_FOUND")
    report = job.reports.get()
    client = APIClient()
    for outsider in [workflow[3], account("buyer"), workflow[4], workflow[6].user]:
        client.force_authenticate(outsider)
        assert client.get(f"/api/v1/full-checks/{job.pk}/").status_code == 404
        assert client.get(f"/api/v1/full-checks/{job.pk}/reports/{report.pk}/").status_code == 404
    client.force_authenticate(workflow[2])
    assert client.get(f"/api/v1/full-checks/{job.pk}/reports/{report.pk}/").status_code == 200
    assert client.patch(f"/api/v1/full-checks/{job.pk}/", {"status": "PASSED"}, format="json").status_code == 405


def test_public_level_expires_without_destroying_history(workflow):
    job = complete(workflow)
    later = job.expires_at + timedelta(seconds=1)
    assert get_effective_verification_level(user=workflow[3], property_record=job.property, at=later) != 3
    assert process_deadlines(at=later) == 1
    assert process_deadlines(at=later) == 0
    assert job.reports.count() == 1 and job.tasks.count() == 4


def test_material_property_change_invalidates_full_check(workflow):
    job = complete(workflow)
    from apps.properties.services import update_property_record
    update_property_record(actor=workflow[3], property_record=job.property, stated_size=job.property.stated_size + 1)
    job.refresh_from_db()
    assert job.invalidated_at
    assert get_effective_verification_level(user=workflow[3], property_record=job.property) != 3
    assert job.reports.count() == 1 and job.result.result == "PASSED"


@pytest.mark.parametrize("timeout", ["consent", "official", "professional"])
def test_deadline_worker_is_repeatable_and_notifies_buyer(workflow, timeout):
    job = paid(workflow) if timeout == "consent" else started(workflow)
    if timeout == "consent":
        VerificationJob.objects.filter(pk=job.pk).update(consent_due_at=timezone.now() - timedelta(seconds=1))
    else:
        if timeout == "official":
            submit_task(actor=workflow[3], task_id=job.tasks.get(kind="SITE_CAPTURE").pk, findings={}, device="phone", capture=valid_capture(workflow[3], job.property))
            task = job.tasks.get(kind="LOCAL_OFFICE")
        else:
            task = job.tasks.get(kind="PROFESSIONAL")
            assign_professional(actor=workflow[1], task_id=task.pk, profile_id=workflow[6].pk)
        VerificationTask.objects.filter(pk=task.pk).update(due_at=timezone.now() - timedelta(seconds=1))
    assert process_deadlines() == 1
    assert process_deadlines() == 0
    job.refresh_from_db()
    assert job.status == "NOT_COMPLETED"


def test_finalization_audit_failure_rolls_back_result_report_level_and_storage(workflow):
    job = under_review(workflow)
    before = set(get_private_media_storage().objects)
    with patch("apps.verification.full_check_services.audit", side_effect=RuntimeError("audit unavailable")):
        with pytest.raises(RuntimeError):
            services.finalize_full_check(actor=workflow[1], job_id=job.pk, result="PASSED", risk_assessment="Reviewed")
    job.refresh_from_db()
    assert job.status == "UNDER_REVIEW"
    assert not VerificationResult.objects.filter(job=job).exists()
    assert not VerificationReport.objects.filter(job=job).exists()
    assert set(get_private_media_storage().objects) == before


def test_duplicate_finalization_preserves_one_result_and_report(workflow):
    job = complete(workflow)
    with pytest.raises(ValidationError):
        services.finalize_full_check(actor=workflow[1], job_id=job.pk, result="PASSED", risk_assessment="Again")
    assert VerificationResult.objects.filter(job=job).count() == 1
    assert job.reports.count() == 1


def test_external_agent_owner_consent_uses_single_use_staff_outbox(workflow):
    manager, verifier, buyer, _, _, _, _ = workflow
    agent = account("agent")
    listing = create_listing_for(agent, lister_kind="AGENT", status="ACTIVE")
    OwnerContact.objects.create(listing=listing, name="External Owner", whatsapp="+255799887766")
    response = services.order_full_check(actor=buyer, listing_id=listing.listing_id, quote_token=services.quote()["quote"], key="agent-order")
    job = VerificationJob.objects.get(pk=response["job_id"])
    services.confirm_full_check_payment(actor=manager, job_id=job.pk, amount=job.fee, reference=job.payment_reference, bank_reference="AGENT-BANK", tax_receipt_number="AGENT-TAX", tax_receipt=pdf(), key="agent-confirm")
    delivery = ConfirmationDelivery.objects.get(purpose="FULL_CHECK_CONSENT")
    token = delivery.delivery_token
    from apps.payments.confirmations import decide as finance_decide
    with pytest.raises(ValidationError):
        finance_decide(delivery_id=delivery.pk, token=token, decision="CONFIRM", key="wrong-domain")
    with pytest.raises(PermissionDenied):
        services.owner_consent(actor=agent, job_id=job.pk, decision="CONFIRM")
    with pytest.raises(PermissionDenied):
        services.external_owner_consent(delivery_id=delivery.pk, token=token, decision="CONFIRM", key="consent")
    mark_sent(actor=manager, delivery_id=delivery.pk)
    first = services.external_owner_consent(delivery_id=delivery.pk, token=token, decision="CONFIRM", key="consent")
    assert first == services.external_owner_consent(delivery_id=delivery.pk, token=token, decision="CONFIRM", key="consent")
    with pytest.raises(PermissionDenied):
        services.external_owner_consent(delivery_id=delivery.pk, token=token, decision="CONFIRM", key="new-consent")
    delivery.refresh_from_db()
    assert delivery.delivery_token == "" and delivery.consumed_at
    assert "token" not in repr(response).lower()


def test_invalid_one_point_capture_does_not_satisfy_site_task(workflow):
    job = started(workflow)
    capture = create_site_capture(actor=workflow[3], property_record=job.property, observed_point=job.property.pin)
    with pytest.raises(ValidationError):
        submit_task(actor=workflow[3], task_id=job.tasks.get(kind="SITE_CAPTURE").pk, findings={}, device="phone", capture=capture)
    assert job.tasks.get(kind="LOCAL_OFFICE").status == "UNASSIGNED"
