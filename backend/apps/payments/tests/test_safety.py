from decimal import Decimal
from unittest.mock import patch
import pytest
from django.db import DatabaseError, transaction, connection
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.commissions.models import RateTable, RateBand
from apps.commissions.services import CommissionService, publish_rate_table
from apps.deals.services import reprice, DealClosingService
from apps.listings.services import create_listing, check_listing_activation_eligibility
from apps.listings.tests.test_services import create_user, create_property_record, grant_role
from apps.listings.tests.test_api import client_for
from apps.payments.models import IdempotencyRecord, BankAccount, PaymentProof, PaymentConfirmation, Payout, ConfirmationDelivery
from apps.payments import services
from apps.payments.confirmations import request_confirmation, mark_sent, decide
from apps.payments.idempotency import Conflict
from apps.media.storage import get_private_media_storage
from apps.leads.tests.test_leads import grant
from .test_workflow import document, finish
from .conftest import bank_values

pytestmark = pytest.mark.django_db


def test_listing_rate_freezes_at_creation(workflow):
    _, agent, manager, _, _, original = workflow
    grant_role(agent, "agent")
    listing = create_listing(actor=agent, property_record=create_property_record(created_by=agent), lister_kind="AGENT", owner_price=100000000, selling_price=120000000)
    assert listing.rate_table_id == original.pk
    newer = RateTable.objects.create(version=2)
    RateBand.objects.create(table=newer, lower=0, upper=None, oweru_rate="0.04", agent_rate="0.06")
    publish_rate_table(actor=manager, table_id=newer.pk)
    listing.refresh_from_db()
    assert listing.rate_table_id == original.pk


def test_database_freezing_guards(closed):
    buyer, _, _, deal = closed
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL database triggers")
    for mutation in [lambda: RateTable.objects.filter(pk=deal.rate_table_id).update(total_rate=Decimal("0.2")), lambda: RateBand.objects.filter(pk=deal.rate_band_id).update(oweru_rate=Decimal("0.04")), lambda: type(deal.listing).objects.filter(pk=deal.listing_id).update(rate_table=None)]:
        with pytest.raises(DatabaseError), transaction.atomic():
            mutation()
    services.submit_proof(actor=buyer, deal_id=deal.pk, transfer="OWNER", upload=document(), key="proof")
    with pytest.raises(DatabaseError), transaction.atomic():
        type(deal).objects.filter(pk=deal.pk).update(final_selling_price=deal.final_selling_price+1, buyer_to_oweru=deal.buyer_to_oweru+1, oweru_keeps=deal.oweru_keeps+1)


def test_completion_rollback_and_payout_constraint(closed):
    buyer, agent, manager, deal = closed
    with patch('apps.payments.services.create_payout', side_effect=RuntimeError("payout unavailable")):
        with pytest.raises(RuntimeError):
            finish(closed)
    deal.refresh_from_db(); deal.lead.refresh_from_db(); deal.listing.refresh_from_db()
    assert deal.state == "OPEN" and deal.lead.stage == "CLOSING" and deal.listing.status == "UNDER_OFFER"
    assert not IdempotencyRecord.objects.filter(operation="deal.complete").exists()
    services.complete_financial_deal(actor=manager, deal_id=deal.pk, key="complete")
    with pytest.raises(DatabaseError), transaction.atomic():
        Payout.objects.filter(deal=deal).update(amount=1)


def test_user_resource_operation_isolation(closed):
    buyer, agent, manager, deal = closed
    other_manager = create_user()
    other_manager.account_category="operational"; other_manager.save()
    grant(other_manager, "management")
    a = services.confirm_receipt(actor=manager, deal_id=deal.pk, transfer="OWERU", bank_reference="B", key="shared")
    b = services.confirm_receipt(actor=other_manager, deal_id=deal.pk, transfer="OWERU", bank_reference="B", key="shared")
    assert a == b
    services.submit_proof(actor=buyer, deal_id=deal.pk, transfer="OWNER", upload=document(), key="shared")
    assert IdempotencyRecord.objects.filter(key="shared").count() == 3
    from apps.listings.tests.test_services import create_listing_for
    from apps.leads.services import create_lead, LeadTransitionService
    from apps.payments.models import OwnerContact
    listing = create_listing_for(agent, lister_kind="AGENT", status="ACTIVE", rate_table=deal.rate_table)
    contact = OwnerContact.objects.create(listing=listing, name="Owner", whatsapp="+255799000090", confirmed_at=timezone.now(), confirmed_owner_price=listing.owner_price, decision="CONFIRM")
    BankAccount.objects.create(owner_contact=contact, **bank_values())
    lead = create_lead(actor=buyer, listing_id=listing.listing_id, source="ENQUIRY")
    for stage in ["CONTACTED", "VIEWING", "NEGOTIATION"]:
        LeadTransitionService.transition(actor=agent, lead_id=lead.pk, stage=stage)
    other = DealClosingService.close(actor=agent, lead_id=lead.pk, final_selling_price=listing.selling_price)
    services.confirm_receipt(actor=manager, deal_id=other.pk, transfer="OWERU", bank_reference="DIFFERENT-DEAL", key="shared")
    assert IdempotencyRecord.objects.filter(key="shared").count() == 4


def test_api_idempotency_http_conflict(closed):
    _, _, manager, deal = closed
    client = client_for(manager)
    url = f'/api/v1/payments/deals/{deal.pk}/confirm/oweru/'
    first = client.post(url, {"bank_reference": "B"}, HTTP_IDEMPOTENCY_KEY="same")
    assert first.status_code == 200
    assert client.post(url, {"bank_reference": "B"}, HTTP_IDEMPOTENCY_KEY="same").data == first.data
    assert client.post(url, {"bank_reference": "other"}, HTTP_IDEMPOTENCY_KEY="same").status_code == 409
    assert client.post(url, {"bank_reference": "B"}).status_code == 400
    assert AuditLog.objects.filter(action="payment.oweru_confirmed").count() == 1


def test_inactive_and_category_inconsistent_users(closed):
    buyer, agent, manager, deal = closed
    User.objects.filter(pk=buyer.pk).update(is_active=False)
    with pytest.raises(PermissionDenied):
        services.submit_proof(actor=buyer, deal_id=deal.pk, transfer="OWNER", upload=document(), key="p")
    manager.account_category="public"; manager.save()
    with pytest.raises(PermissionDenied):
        services.confirm_receipt(actor=manager, deal_id=deal.pk, transfer="OWERU", bank_reference="B", key="p")


@pytest.mark.parametrize("upload", [
    lambda: SimpleUploadedFile("proof.exe", b"%PDF-1.4\n%%EOF", content_type="application/pdf"),
    lambda: SimpleUploadedFile("proof.pdf", b"not a PDF", content_type="application/pdf"),
    lambda: SimpleUploadedFile("proof.pdf", b"%PDF-1.4\n%%EOF", content_type="image/png"),
])
def test_invalid_proof_type(closed, upload):
    buyer, _, _, deal = closed
    with pytest.raises(ValidationError):
        services.submit_proof(actor=buyer, deal_id=deal.pk, transfer="OWNER", upload=upload(), key="x")
    assert PaymentProof.objects.count() == 0


def test_storage_cleanup_on_rollback(closed):
    buyer, _, _, deal = closed
    storage = get_private_media_storage()
    with patch('apps.payments.services.audit', side_effect=RuntimeError("audit")):
        with pytest.raises(RuntimeError):
            services.submit_proof(actor=buyer, deal_id=deal.pk, transfer="OWNER", upload=document(), key="retry")
    assert not storage.objects and not PaymentProof.objects.exists()


def test_owner_listing_authenticated_confirmation(closed):
    buyer, agent, manager, _ = closed
    owner = create_user(); grant(owner, "owner")
    BankAccount.objects.create(user=owner, **bank_values())
    from apps.listings.tests.test_services import create_listing_for
    from apps.leads.services import create_lead, LeadTransitionService
    from apps.commissions.services import current_rate_table
    listing = create_listing_for(owner, status="ACTIVE", rate_table=current_rate_table())
    lead = create_lead(actor=buyer, listing_id=listing.listing_id, source="ENQUIRY")
    for stage in ["CONTACTED", "VIEWING", "NEGOTIATION"]:
        LeadTransitionService.transition(actor=owner, lead_id=lead.pk, stage=stage)
    deal = DealClosingService.close(actor=owner, lead_id=lead.pk, final_selling_price=100000000)
    values = dict(actor=owner, deal_id=deal.pk, transfer="OWNER", bank_reference="B", key="owner")
    first = services.confirm_receipt(**values)
    assert services.confirm_receipt(**values) == first
    assert services.confirm_receipt(**{**values, "key": "other"}) == first
    assert deal.buyer_to_owner == 97000000 and deal.buyer_to_oweru == 3000000
    assert AuditLog.objects.filter(action="payment.owner_confirmed").count() == 1


def test_external_owner_replay_and_conflict(closed):
    _, agent, manager, deal = closed
    request = request_confirmation(actor=agent, purpose="OWNER_RECEIPT", deal_id=deal.pk)
    delivery = ConfirmationDelivery.objects.get(pk=request["delivery_id"])
    token = delivery.delivery_token
    mark_sent(actor=manager, delivery_id=delivery.pk)
    values = dict(delivery_id=delivery.pk, token=token, decision="CONFIRM", bank_reference="B", key="k")
    first = decide(**values)
    assert decide(**values) == first
    with pytest.raises(Conflict):
        decide(**{**values, "bank_reference": "other"})
    assert PaymentConfirmation.objects.filter(deal=deal, transfer="OWNER").count() == 1
    assert AuditLog.objects.filter(action="payment.owner_confirmed").count() == 1
