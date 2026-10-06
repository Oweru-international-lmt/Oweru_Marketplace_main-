from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from unittest.mock import patch
import pytest
from django.db import connection, close_old_connections
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.deals.services import DealClosingService
from apps.deals.models import Deal
from apps.payments.services import confirm_receipt, submit_proof, payout_action, complete_financial_deal, mark_due_payouts
from apps.payments.models import PaymentConfirmation, PaymentProof, IdempotencyRecord, Payout
from .test_workflow import document, finish

pytestmark = pytest.mark.django_db(transaction=True)


def concurrent(call):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row-locking proof required")
    barrier = Barrier(2)
    def run():
        close_old_connections()
        try:
            barrier.wait(timeout=15)
            return call()
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as executor:
        first, second = executor.submit(run), executor.submit(run)
        return first.result(timeout=30), second.result(timeout=30)


def test_concurrent_closing(workflow):
    _, agent, _, _, lead, _ = workflow
    results = concurrent(lambda: str(DealClosingService.close(actor=User.objects.get(pk=agent.pk), lead_id=lead.pk, final_selling_price=120000000).pk))
    assert results[0] == results[1]
    assert Deal.objects.count() == 1
    assert AuditLog.objects.filter(action="deal.created").count() == 1


def test_concurrent_same_key_confirmation(closed):
    _, _, manager, deal = closed
    results = concurrent(lambda: confirm_receipt(actor=User.objects.get(pk=manager.pk), deal_id=deal.pk, transfer="OWERU", bank_reference="BANK", key="same-key"))
    assert results[0] == results[1]
    assert PaymentConfirmation.objects.count() == 1
    assert IdempotencyRecord.objects.filter(operation="payment.confirm.OWERU").count() == 1
    assert AuditLog.objects.filter(action="payment.oweru_confirmed").count() == 1


def test_concurrent_same_key_proof(closed):
    buyer, _, _, deal = closed
    results = concurrent(lambda: submit_proof(actor=User.objects.get(pk=buyer.pk), deal_id=deal.pk, transfer="OWNER", upload=document(), key="same-key"))
    assert results[0] == results[1]
    assert PaymentProof.objects.count() == 1
    assert AuditLog.objects.filter(action="payment.proof_submitted").count() == 1


def test_concurrent_payout_paid(closed):
    _, _, manager, deal = closed
    finish(closed)
    results = concurrent(lambda: payout_action(actor=User.objects.get(pk=manager.pk), deal_id=deal.pk, action="paid", bank_reference="BANK", upload=document(), key="same-key"))
    assert results[0] == results[1]
    assert Payout.objects.get(deal=deal).status == "PAID"
    assert AuditLog.objects.filter(action="payout.paid").count() == 1


def test_concurrent_completion_creates_one_payout(closed):
    _, _, manager, deal = closed
    with patch('apps.payments.services.complete_financial_deal', return_value={}):
        finish(closed)
    results = concurrent(lambda: complete_financial_deal(actor=User.objects.get(pk=manager.pk), deal_id=deal.pk, key="complete"))
    assert results[0] == results[1]
    assert Payout.objects.filter(deal=deal).count() == 1
    assert AuditLog.objects.filter(action="payout.created").count() == 1
    assert AuditLog.objects.filter(action="deal.completed").count() == 1


def test_concurrent_due_job_is_idempotent(closed):
    finish(closed)
    due_at = Payout.objects.get(deal=closed[-1]).due_at
    results = concurrent(lambda: mark_due_payouts(at=due_at))
    assert sum(results) == 1
    assert AuditLog.objects.filter(action="payout.due").count() == 1


def test_publication_waits_for_listing_creation(workflow, monkeypatch):
    from concurrent.futures import TimeoutError
    from apps.listings import services as listing_services
    from apps.listings.tests.test_services import grant_role, create_property_record
    from apps.commissions.models import RateTable, RateBand
    from apps.commissions.services import publish_rate_table
    _, agent, manager, _, _, old = workflow
    grant_role(agent, "agent")
    property_record = create_property_record(created_by=agent)
    draft = RateTable.objects.create(version=2)
    RateBand.objects.create(table=draft, lower=0, upper=None, oweru_rate="0.04", agent_rate="0.06")
    selected, release, publishing = Event(), Event(), Event()
    validate = listing_services._validate_listing
    def pause(listing):
        selected.set()
        assert release.wait(timeout=15)
        validate(listing)
    monkeypatch.setattr(listing_services, '_validate_listing', pause)
    def create():
        close_old_connections()
        try:
            return listing_services.create_listing(actor=User.objects.get(pk=agent.pk), property_record=property_record.pk, lister_kind="AGENT", owner_price=100000000, selling_price=120000000)
        finally:
            close_old_connections()
    def publish():
        close_old_connections()
        try:
            publishing.set()
            return publish_rate_table(actor=User.objects.get(pk=manager.pk), table_id=draft.pk)
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as executor:
        creation = executor.submit(create)
        assert selected.wait(timeout=15)
        publication = executor.submit(publish)
        assert publishing.wait(timeout=15)
        try:
            with pytest.raises(TimeoutError):
                publication.result(timeout=0.2)
        finally:
            release.set()
        listing = creation.result(timeout=30)
        published = publication.result(timeout=30)
    assert listing.rate_table_id == old.pk and listing.created_at <= published.published_at
