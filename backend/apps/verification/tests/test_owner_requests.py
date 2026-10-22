import pytest
from rest_framework.test import APIClient

from apps.listings.tests.test_services import create_listing_for
from apps.payments.models import BankAccount
from apps.professionals.tests.test_professionals import account, pdf, storage  # noqa: F401
from apps.verification import full_check_services as services
from apps.verification.models import FullCheckReceipt, VerificationJob, VerificationSetting

pytestmark = pytest.mark.django_db


@pytest.fixture
def workflow():
    # The fee row is written directly: change_setting takes a PostgreSQL-only lock.
    manager, buyer, owner = [account(role) for role in ["management", "buyer", "owner"]]
    listing = create_listing_for(owner, lister_kind="OWNER", status="ACTIVE")
    VerificationSetting.objects.create(key="full_check_fee", value="100000", changed_by=manager, version=1)
    BankAccount.objects.create(is_oweru=True, bank_name="Bank", account_name="Oweru", account_number="12345", branch="Dar")
    return manager, None, buyer, owner, None, listing, None


def order(workflow, key="order"):
    _, _, buyer, _, _, listing, _ = workflow
    response = services.order_full_check(actor=buyer, listing_id=listing.listing_id, quote_token=services.quote()["quote"], key=key)
    return VerificationJob.objects.get(pk=response["job_id"])


def client(user):
    api = APIClient()
    api.force_authenticate(user)
    return api


def test_payment_confirms_without_a_tax_receipt_and_owner_sees_the_request(workflow):
    manager, _, _, owner, _, _, _ = workflow
    job = order(workflow)
    services.confirm_full_check_payment(actor=manager, job_id=job.pk, amount=job.fee, reference=job.payment_reference, bank_reference="BANK-NO-TAX", key="no-tax")
    receipt = FullCheckReceipt.objects.get(job=job)
    assert receipt.tax_receipt_id is None and receipt.tax_receipt_number is None

    rows = client(owner).get("/api/v1/full-checks/requests/").data
    assert [(row["kind"], row["job_id"]) for row in rows] == [("consent", str(job.pk))]
    assert client(owner).post(f"/api/v1/full-checks/{job.pk}/owner-consent/", {"decision": "CONFIRM"}, format="json").data["status"] == "IN_PROGRESS"
    assert client(owner).get("/api/v1/full-checks/requests/").data == []


def test_tax_receipt_copy_needs_its_number(workflow):
    manager = workflow[0]
    job = order(workflow)
    with pytest.raises(Exception):
        services.confirm_full_check_payment(actor=manager, job_id=job.pk, amount=job.fee, reference=job.payment_reference, bank_reference="BANK", tax_receipt=pdf(), key="copy-only")


def test_agent_without_owner_contact_supplies_it_from_the_requests_list(workflow):
    manager, _, buyer, _, _, _, _ = workflow
    agent = account("agent")
    listing = create_listing_for(agent, lister_kind="AGENT", status="ACTIVE")
    response = services.order_full_check(actor=buyer, listing_id=listing.listing_id, quote_token=services.quote()["quote"], key="agent-order")
    job = VerificationJob.objects.get(pk=response["job_id"])
    services.confirm_full_check_payment(actor=manager, job_id=job.pk, amount=job.fee, reference=job.payment_reference, bank_reference="AGENT-BANK", key="agent-confirm")

    rows = client(agent).get("/api/v1/full-checks/requests/").data
    assert [(row["kind"], row["job_id"]) for row in rows] == [("contact", str(job.pk))]
    assert client(buyer).get("/api/v1/full-checks/requests/").data == []
    sent = client(agent).post(f"/api/v1/full-checks/{job.pk}/owner-contact/", {"owner_name": "Mzee Hamisi", "owner_phone": "+255744100200"}, format="json")
    assert sent.status_code == 200, sent.data
    assert client(agent).get("/api/v1/full-checks/requests/").data == []
