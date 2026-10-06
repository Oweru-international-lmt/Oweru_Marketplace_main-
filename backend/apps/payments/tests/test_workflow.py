from decimal import Decimal
from datetime import datetime
from unittest.mock import patch
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.audit.models import AuditLog
from apps.leads.models import Lead, LostLeadReview
from apps.leads.services import LeadTransitionService, review_lost_sales
from apps.deals.models import Deal
from apps.deals.services import DealClosingService, reprice
from apps.commissions.models import RateTable, RateBand
from apps.commissions.services import CommissionService, publish_rate_table
from apps.payments import services
from apps.payments.models import ConfirmationDelivery, IdempotencyRecord, PaymentProof, PaymentConfirmation, OfficialTaxReceipt, Payout, PhoneConfirmation
from apps.payments.confirmations import request_confirmation, mark_sent, decide
from apps.payments.idempotency import Conflict
from apps.roles.legacy_authorization.models import UserRole
from apps.listings.tests.test_api import client_for
from apps.listings.tests.test_services import create_user, grant_role, create_listing_for
from apps.leads.tests.test_leads import grant
from .conftest import bank_values

pytestmark = pytest.mark.django_db


def document(content=b"evidence"):
    return SimpleUploadedFile("proof.pdf", b"%PDF-1.4\n" + content + b"\n%%EOF", content_type="application/pdf")


def finish(closed):
    buyer, agent, manager, deal = closed
    for transfer in ["OWNER", "OWERU"]:
        services.submit_proof(actor=buyer, deal_id=deal.pk, transfer=transfer, upload=document(transfer.encode()), key=transfer)
    delivery = request_confirmation(actor=agent, purpose="OWNER_RECEIPT", deal_id=deal.pk)
    row = ConfirmationDelivery.objects.get(pk=delivery["delivery_id"])
    token = row.delivery_token
    mark_sent(actor=manager, delivery_id=row.pk)
    decide(delivery_id=row.pk, token=token, decision="CONFIRM", bank_reference="OWNER-BANK", key="owner-receipt")
    services.confirm_receipt(actor=manager, deal_id=deal.pk, transfer="OWERU", bank_reference="OWERU-BANK", key="oweru")
    services.agreement_action(actor=agent, deal_id=deal.pk, action="upload", upload=document(b"signed agreement 120000000"), key="agreement")
    services.agreement_action(actor=agent, deal_id=deal.pk, action="confirm", key="agreement-confirm")
    services.agreement_action(actor=manager, deal_id=deal.pk, action="approve", key="agreement-approve")
    services.complete_financial_deal(actor=manager, deal_id=deal.pk, key="complete")
    deal.refresh_from_db()
    return deal


def test_end_to_end_acceptance(closed):
    buyer, agent, manager, deal = closed
    assert deal.lead.stage == "CLOSING"
    assert deal.listing.status == "UNDER_OFFER"
    assert (deal.buyer_to_owner, deal.buyer_to_oweru, deal.oweru_keeps, deal.agent_payout) == (90000000, 30000000, 3000000, 27000000)
    instruction = services.instructions(actor=buyer, deal_id=deal.pk)
    assert Decimal(instruction["owner"]["amount"]) + Decimal(instruction["oweru"]["amount"]) == deal.final_selling_price
    assert instruction["oweru"]["reference"] == deal.payment_reference
    deal = finish(closed)
    deal.lead.refresh_from_db()
    deal.listing.refresh_from_db()
    assert deal.state == "COMPLETE" and deal.lead.stage == "WON" and deal.listing.status == "SOLD"
    payout = deal.payout
    assert payout.status == "PENDING" and payout.amount == 27000000
    assert services.mark_due_payouts(at=payout.due_at) == 1
    assert services.mark_due_payouts(at=payout.due_at) == 0
    payout.refresh_from_db()
    assert payout.status == "DUE"
    result = services.payout_action(actor=manager, deal_id=deal.pk, action="paid", bank_reference="PAYOUT-BANK", upload=document(b"payout"), key="paid")
    assert result["status"] == "PAID"


def test_closing_duplicate_and_rollback(workflow):
    _, agent, _, listing, lead, _ = workflow
    with patch('apps.deals.services.audit', side_effect=RuntimeError("audit failure")):
        with pytest.raises(RuntimeError):
            DealClosingService.close(actor=agent, lead_id=lead.pk, final_selling_price=120000000)
    lead.refresh_from_db(); listing.refresh_from_db()
    assert lead.stage == "NEGOTIATION" and listing.status == "ACTIVE" and Deal.objects.count() == 0
    first = DealClosingService.close(actor=agent, lead_id=lead.pk, final_selling_price=120000000)
    second = DealClosingService.close(actor=agent, lead_id=lead.pk, final_selling_price=120000000)
    assert first.pk == second.pk and Deal.objects.count() == 1


@pytest.mark.parametrize("missing", ["price", "owner", "rate", "state"])
def test_closing_prerequisites(workflow, missing):
    _, agent, _, listing, lead, _ = workflow
    price = None if missing == "price" else 120000000
    if missing == "owner":
        listing.owner_contact.confirmed_at = None
        listing.owner_contact.save()
    if missing == "rate":
        missing_rate_listing = create_listing_for(agent, lister_kind="AGENT", status="ACTIVE", property=listing.property)
        lead.listing = missing_rate_listing
        lead.save(update_fields=["listing"])
    if missing == "state":
        lead.stage = "NEW"; lead.save()
    with pytest.raises(ValidationError):
        DealClosingService.close(actor=agent, lead_id=lead.pk, final_selling_price=price)
    assert not Deal.objects.exists()


def test_owner_formula_and_rounding(workflow):
    *_, table = workflow
    values = CommissionService.calculate(owner_price=1, selling_price=100000000, rate_table=table, lister_kind="OWNER")
    assert values["buyer_to_owner"] == 97000000 and values["buyer_to_oweru"] == 3000000 and values["agent_payout"] == 0
    for price in [1, 5, 11, 50000000, 50000001, 100000001]:
        for kind in ["OWNER", "AGENT"]:
            result = CommissionService.calculate(owner_price=price, selling_price=price, rate_table=table, lister_kind=kind)
            assert result["buyer_to_owner"] + result["buyer_to_oweru"] == price
            assert result["oweru_keeps"] + result["agent_payout"] == result["buyer_to_oweru"]
    with pytest.raises(ValidationError):
        CommissionService.calculate(owner_price=1.0, selling_price=2, rate_table=table, lister_kind="AGENT")


@pytest.mark.parametrize("lower", [49999999, 50000002])
def test_rate_overlap_gap(workflow, lower):
    _, _, manager, _, _, _ = workflow
    table = RateTable.objects.create(version=2)
    RateBand.objects.create(table=table, lower=0, upper=50000000, oweru_rate="0.03", agent_rate="0.07")
    RateBand.objects.create(table=table, lower=lower, upper=None, oweru_rate="0.03", agent_rate="0.07")
    with pytest.raises(ValidationError):
        publish_rate_table(actor=manager, table_id=table.pk)


def test_historical_version(workflow):
    _, agent, manager, listing, lead, original = workflow
    new = RateTable.objects.create(version=2)
    RateBand.objects.create(table=new, lower=0, upper=None, oweru_rate="0.04", agent_rate="0.06")
    publish_rate_table(actor=manager, table_id=new.pk)
    deal = DealClosingService.close(actor=agent, lead_id=lead.pk, final_selling_price=120000000)
    assert deal.rate_table_id == original.pk and deal.oweru_rate == Decimal("0.03")


def test_reprice_freezes_on_activity(closed):
    buyer, agent, _, deal = closed
    reprice(actor=agent, deal_id=deal.pk, final_selling_price=130000000)
    services.submit_proof(actor=buyer, deal_id=deal.pk, transfer="OWNER", upload=document(), key="proof")
    with pytest.raises(ValidationError):
        reprice(actor=agent, deal_id=deal.pk, final_selling_price=140000000)


def test_security(closed):
    buyer, agent, manager, deal = closed
    stranger = create_user(); grant(stranger, "buyer")
    assert client_for(stranger).get(f'/api/v1/deals/{deal.pk}/').status_code == 404
    assert client_for(agent).get(f'/api/v1/payments/deals/{deal.pk}/instructions/').status_code == 403
    assert client_for(agent).get(f'/api/v1/payments/bank-account/').status_code == 404
    for actor, transfer in [(buyer, "OWERU"), (agent, "OWNER")]:
        with pytest.raises(PermissionDenied):
            services.confirm_receipt(actor=actor, deal_id=deal.pk, transfer=transfer, bank_reference="B", key="x")
    with pytest.raises(PermissionDenied):
        services.complete_financial_deal(actor=buyer, deal_id=deal.pk, key="x")
    with pytest.raises(ValidationError):
        services.complete_financial_deal(actor=manager, deal_id=deal.pk, key="x")
    assert client_for(agent).patch(f'/api/v1/leads/{deal.lead_id}/', {"stage": "WON"}).status_code == 405
    assert client_for(agent).post(f'/api/v1/payouts/deals/{deal.pk}/paid/', {"amount": "1"}).status_code == 400
    UserRole.objects.filter(user=manager).update(is_active=False)
    with pytest.raises(PermissionDenied):
        services.confirm_receipt(actor=manager, deal_id=deal.pk, transfer="OWERU", bank_reference="B", key="x")


def test_private_documents_and_api_tampering(closed):
    buyer, agent, manager, deal = closed
    result = services.submit_proof(actor=buyer, deal_id=deal.pk, transfer="OWERU", upload=document(), key="x")
    assert "file_key" not in str(result) and "financial/" not in str(result)
    assert client_for(agent).get(f'/api/v1/deals/{deal.pk}/documents/{result["media_id"]}/').status_code == 404
    response = client_for(buyer).get(f'/api/v1/deals/{deal.pk}/documents/{result["media_id"]}/')
    assert response.status_code == 200 and "financial/" not in str(response.data)
    assert client_for(buyer).get(f'/api/v1/media/{result["media_id"]}/').status_code in {403, 404}
    response = client_for(agent).post(f'/api/v1/deals/{deal.pk}/final-price/', {"final_selling_price": 130000000, "agent_payout": 1}, HTTP_IDEMPOTENCY_KEY="z")
    assert response.status_code == 400


def test_idempotency_proof_conflict_retry(closed):
    buyer, _, _, deal = closed
    values = dict(actor=buyer, deal_id=deal.pk, transfer="OWNER", key="proof")
    first = services.submit_proof(upload=document(), **values)
    assert services.submit_proof(upload=document(), **values) == first
    assert services.submit_proof(upload=document(), **{**values, "key": "other"}) == first
    assert PaymentProof.objects.count() == 1
    assert AuditLog.objects.filter(action="payment.proof_submitted").count() == 1
    with pytest.raises(Conflict):
        services.submit_proof(upload=document(b"changed"), **values)
    with patch('apps.payments.services.audit', side_effect=RuntimeError("audit")):
        with pytest.raises(RuntimeError):
            services.submit_proof(upload=document(b"retry"), **{**values, "key": "retry"})
    assert not IdempotencyRecord.objects.filter(key="retry").exists()
    services.submit_proof(upload=document(b"retry"), **{**values, "key": "retry"})
    assert PaymentProof.objects.count() == 2


def test_idempotency_confirm_tax_complete_payout(closed):
    buyer, agent, manager, deal = closed
    values = dict(actor=manager, deal_id=deal.pk, transfer="OWERU", bank_reference="B", key="confirm")
    first = services.confirm_receipt(**values)
    assert services.confirm_receipt(**values) == first
    assert services.confirm_receipt(**{**values, "key": "other"}) == first
    assert PaymentConfirmation.objects.count() == 1
    assert AuditLog.objects.filter(action="payment.oweru_confirmed").count() == 1
    receipt = dict(actor=manager, deal_id=deal.pk, number="EFD123", kind="EFD", key="tax")
    first = services.record_tax_receipt(upload=document(), **receipt)
    assert services.record_tax_receipt(upload=document(), **receipt) == first
    assert services.record_tax_receipt(upload=document(), **{**receipt, "key": "other"}) == first
    assert OfficialTaxReceipt.objects.count() == 1
    # Continue without the existing different Oweru reference in finish().
    PaymentConfirmation.objects.filter(transfer="OWERU").update(bank_reference="OWERU-BANK")
    deal = finish(closed)
    assert services.complete_financial_deal(actor=manager, deal_id=deal.pk, key="complete")["state"] == "COMPLETE"
    payout = services.payout_action(actor=manager, deal_id=deal.pk, action="create", key="create")
    assert services.payout_action(actor=manager, deal_id=deal.pk, action="create", key="create") == payout
    assert Payout.objects.count() == 1
    paid = dict(actor=manager, deal_id=deal.pk, action="paid", bank_reference="P", key="paid")
    first = services.payout_action(upload=document(), **paid)
    assert services.payout_action(upload=document(), **paid) == first
    assert services.payout_action(upload=document(), **{**paid, "key": "another"}) == first
    assert AuditLog.objects.filter(action="payout.paid").count() == 1


def test_payout_holds_working_days(closed):
    _, _, manager, deal = closed
    deal = finish(closed)
    start = timezone.make_aware(datetime(2026, 10, 9, 12)) # Friday
    assert services.working_deadline(start, 3).date().isoformat() == "2026-10-14"
    services.set_complaint_block(actor=manager, deal_id=deal.pk, external_reference="CMP-1", is_open=True, key="open")
    for action in ["paid", "release"]:
        with pytest.raises(ValidationError):
            services.payout_action(actor=manager, deal_id=deal.pk, action=action, bank_reference="B", upload=document() if action == "paid" else None, key=action)
    services.set_complaint_block(actor=manager, deal_id=deal.pk, external_reference="CMP-1", is_open=False, key="closed")
    services.payout_action(actor=manager, deal_id=deal.pk, action="release", key="release")
    services.payout_action(actor=manager, deal_id=deal.pk, action="hold", reason="Finance review", key="hold")
    with pytest.raises(ValidationError):
        services.payout_action(actor=manager, deal_id=deal.pk, action="paid", bank_reference="B", upload=document(), key="paid")


def test_phone_and_owner_token_security(workflow):
    _, agent, manager, listing, _, _ = workflow
    delivery = request_confirmation(actor=agent, purpose="PHONE")
    assert "token" not in delivery
    row = ConfirmationDelivery.objects.get(pk=delivery["delivery_id"])
    token = row.delivery_token
    with pytest.raises(PermissionDenied):
        decide(delivery_id=row.pk, token=token, decision="CONFIRM", key="p")
    mark_sent(actor=manager, delivery_id=row.pk)
    first = decide(delivery_id=row.pk, token=token, decision="CONFIRM", key="p")
    assert decide(delivery_id=row.pk, token=token, decision="CONFIRM", key="p") == first
    assert PhoneConfirmation.objects.filter(user=agent, phone=agent.phone).exists()
    with pytest.raises(PermissionDenied):
        decide(delivery_id=row.pk, token=token, decision="CONFIRM", key="different")
    with pytest.raises(PermissionDenied):
        mark_sent(actor=agent, delivery_id=row.pk)


def test_lost_sold_review(closed):
    buyer, agent, _, deal = closed
    lost = Lead.objects.create(listing=deal.listing, property=deal.property, buyer=buyer, lister=agent, buyer_name=buyer.full_name, buyer_whatsapp=buyer.phone, source="ENQUIRY", stage="LOST", lost_at=timezone.now())
    deal = finish(closed)
    assert LostLeadReview.objects.filter(lost_lead=lost, sold_deal=deal).count() == 1
    assert review_lost_sales(deal) == 0
