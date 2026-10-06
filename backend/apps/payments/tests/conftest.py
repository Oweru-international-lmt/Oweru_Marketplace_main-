import pytest
from decimal import Decimal
from django.test import override_settings
from apps.listings.tests.test_services import create_user, create_listing_for
from apps.leads.tests.test_leads import grant
from apps.leads.services import create_lead, LeadTransitionService
from apps.commissions.models import RateTable, RateBand
from apps.commissions.services import publish_rate_table
from apps.payments.models import BankAccount, ConfirmationDelivery
from apps.payments.confirmations import request_confirmation, mark_sent, decide
from apps.media.storage import reset_in_memory_storage


def bank_values():
    return {"bank_name": "Test Bank", "account_name": "Test Holder", "account_number": "123456789", "branch": "Dar"}


@pytest.fixture(autouse=True)
def private_storage():
    reset_in_memory_storage()
    with override_settings(MEDIA_STORAGE_BACKEND="memory", OWNER_CONFIRMATION_URL="https://example.test/confirm"):
        yield
    reset_in_memory_storage()


@pytest.fixture
def workflow():
    buyer, agent, manager = create_user(), create_user(), create_user()
    manager.account_category = "operational"
    manager.save(update_fields=["account_category"])
    grant(buyer, "buyer")
    grant(agent, "agent")
    grant(manager, "management")
    table = RateTable.objects.create(version=1, total_rate=Decimal("0.10"))
    RateBand.objects.create(table=table, lower=0, upper=50000000, oweru_rate=Decimal("0.04"), agent_rate=Decimal("0.06"))
    RateBand.objects.create(table=table, lower=50000001, upper=None, oweru_rate=Decimal("0.03"), agent_rate=Decimal("0.07"))
    table = publish_rate_table(actor=manager, table_id=table.pk)
    listing = create_listing_for(agent, lister_kind="AGENT", status="ACTIVE", selling_price=Decimal(120000000), owner_price=Decimal(100000000), rate_table=table)
    BankAccount.objects.create(is_oweru=True, **bank_values())
    delivery = request_confirmation(actor=agent, purpose="OWNER_PRICE", listing_id=listing.listing_id, owner_name="External Owner", owner_whatsapp="+255799000009")
    row = ConfirmationDelivery.objects.get(pk=delivery["delivery_id"])
    token = row.delivery_token
    mark_sent(actor=manager, delivery_id=row.pk)
    decide(delivery_id=row.pk, token=token, decision="CONFIRM", bank=bank_values(), key="owner-price")
    lead = create_lead(actor=buyer, listing_id=listing.listing_id, source="ENQUIRY")
    for stage in ["CONTACTED", "VIEWING", "NEGOTIATION"]:
        LeadTransitionService.transition(actor=agent, lead_id=lead.pk, stage=stage)
    return buyer, agent, manager, listing, lead, table


@pytest.fixture
def closed(workflow):
    from apps.deals.services import DealClosingService
    buyer, agent, manager, listing, lead, table = workflow
    deal = DealClosingService.close(actor=agent, lead_id=lead.pk, final_selling_price=Decimal(120000000))
    return buyer, agent, manager, deal
