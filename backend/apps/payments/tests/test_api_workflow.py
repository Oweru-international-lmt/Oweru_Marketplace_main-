import pytest
from apps.listings.tests.test_api import client_for
from apps.listings.tests.test_services import create_user
from apps.leads.tests.test_leads import grant
from apps.leads.services import create_lead, LeadTransitionService
from apps.payments.models import ConfirmationDelivery, PaymentProof, Payout, BankAccount
from apps.payments import services
from apps.audit.models import AuditLog
from .conftest import bank_values
from .test_workflow import document, finish

pytestmark = pytest.mark.django_db


def test_api_full_acceptance(workflow):
    buyer, agent, manager, listing, lead, _ = workflow
    buyer_client, agent_client, manager_client = map(client_for, [buyer, agent, manager])
    url = f'/api/v1/leads/{lead.pk}/transition/'
    close_payload = {"stage": "CLOSING", "final_selling_price": "120000000"}
    first = agent_client.post(url, close_payload, HTTP_IDEMPOTENCY_KEY="closing")
    assert first.status_code == 200
    assert agent_client.post(url, close_payload, HTTP_IDEMPOTENCY_KEY="closing").data == first.data
    assert agent_client.post(url, {**close_payload, "final_selling_price": "130000000"}, HTTP_IDEMPOTENCY_KEY="closing").status_code == 409
    deal = lead.deal
    assert buyer_client.get(f'/api/v1/payments/deals/{deal.pk}/instructions/').status_code == 200
    for transfer in ["OWNER", "OWERU"]:
        response = buyer_client.post(f'/api/v1/payments/deals/{deal.pk}/proofs/', {"transfer": transfer, "file": document(transfer.encode())}, format="multipart", HTTP_IDEMPOTENCY_KEY=transfer)
        assert response.status_code == 200
    response = agent_client.post('/api/v1/payments/confirmation-requests/', {"purpose": "OWNER_RECEIPT", "deal_id": str(deal.pk)}, format="json")
    assert response.status_code == 201 and "token" not in str(response.data)
    delivery = ConfirmationDelivery.objects.get(pk=response.data["delivery_id"])
    token = delivery.delivery_token
    assert agent_client.get('/api/v1/management/finance/outbox/').status_code == 403
    outbox = manager_client.get('/api/v1/management/finance/outbox/')
    assert outbox.status_code == 200 and len(outbox.data) == 1
    assert manager_client.post(f'/api/v1/management/finance/outbox/{delivery.pk}/sent/', {}).status_code == 200
    from rest_framework.test import APIClient
    external = APIClient()
    assert external.get(f'/api/v1/payments/confirmations/{delivery.pk}/', {"token": token}).status_code == 200
    assert external.post(f'/api/v1/payments/confirmations/{delivery.pk}/', {"token": token, "decision": "CONFIRM", "bank_reference": "OWNER-B"}, format="json", HTTP_IDEMPOTENCY_KEY="owner").status_code == 200
    assert manager_client.post(f'/api/v1/payments/deals/{deal.pk}/confirm/oweru/', {"bank_reference": "OWERU-B"}, HTTP_IDEMPOTENCY_KEY="oweru").status_code == 200
    assert agent_client.post(f'/api/v1/deals/{deal.pk}/agreement/upload/', {"file": document(b"signed")}, format="multipart", HTTP_IDEMPOTENCY_KEY="agreement").status_code == 200
    for client, action in [(agent_client, "confirm"), (manager_client, "approve")]:
        assert client.post(f'/api/v1/deals/{deal.pk}/agreement/{action}/', {"confirms_exact_final_price": True}, format="json", HTTP_IDEMPOTENCY_KEY=action).status_code == 200
    assert manager_client.post(f'/api/v1/deals/{deal.pk}/complete/', {}, HTTP_IDEMPOTENCY_KEY="complete").status_code == 200
    payout = Payout.objects.get(deal=deal)
    services.mark_due_payouts(at=payout.due_at)
    assert manager_client.post(f'/api/v1/payouts/deals/{deal.pk}/paid/', {"bank_reference": "PAID-B", "file": document(b"paid")}, format="multipart", HTTP_IDEMPOTENCY_KEY="paid").status_code == 200


def test_unpaid_closing_can_be_lost(closed):
    _, agent, _, deal = closed
    LeadTransitionService.transition(actor=agent, lead_id=deal.lead_id, stage="LOST", reason="Buyer withdrew")
    deal.refresh_from_db(); deal.listing.refresh_from_db(); deal.lead.refresh_from_db()
    assert deal.state == "CANCELLED" and deal.listing.status == "ACTIVE" and deal.lead.stage == "LOST"


def test_external_customer_snapshot_and_metrics(workflow):
    _, agent, _, listing, _, _ = workflow
    lead = create_lead(actor=agent, listing_id=listing.listing_id, source="WHATSAPP_CONTACT", buyer_name="External Customer", buyer_whatsapp="+255799009999")
    assert lead.buyer is None and lead.buyer_name == "External Customer"
    response = client_for(agent).get('/api/v1/leads/metrics/')
    assert response.status_code == 200 and response.data["enquiries"] == 2 and response.data["viewings"] == 1


def test_bank_idempotency_and_snapshot_privacy(closed):
    buyer, agent, _, deal = closed
    client = client_for(agent)
    first = client.put('/api/v1/payments/bank-account/', bank_values(), format="json", HTTP_IDEMPOTENCY_KEY="bank")
    assert first.status_code == 200
    assert client.put('/api/v1/payments/bank-account/', bank_values(), format="json", HTTP_IDEMPOTENCY_KEY="bank").data == first.data
    assert client.put('/api/v1/payments/bank-account/', {**bank_values(), "account_number": "different"}, format="json", HTTP_IDEMPOTENCY_KEY="bank").status_code == 409
    assert AuditLog.objects.filter(action="bank_account.updated").count() == 1
    instructions = services.instructions(actor=buyer, deal_id=deal.pk)
    BankAccount.objects.filter(owner_contact__listing=deal.listing).update(account_number="changed-after-closing")
    assert services.instructions(actor=buyer, deal_id=deal.pk)["owner"] == instructions["owner"]
    assert "bank_snapshot" not in str(client.get(f'/api/v1/deals/{deal.pk}/').data)
