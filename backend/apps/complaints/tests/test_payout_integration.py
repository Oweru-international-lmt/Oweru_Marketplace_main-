import pytest
from apps.payments.tests.test_workflow import finish
from apps.payments.tests.conftest import closed, workflow
from apps.professionals.tests.test_professionals import storage
from apps.payments.models import Payout, PayoutBlock
from apps.payments.services import payout_action
from rest_framework.exceptions import ValidationError
from apps.complaints.services import lodge, transition, request_final_review, token_for
from .test_complaints import inputs, move

pytestmark = pytest.mark.django_db


def test_open_complaint_before_completion_holds_future_payout(closed):
    buyer, agent, manager, deal = closed
    row = lodge(values=inputs(deal_id=str(deal.pk)))
    assert PayoutBlock.objects.get(deal=deal).is_open
    finish(closed)
    with pytest.raises(ValidationError):
        payout_action(actor=manager, deal_id=deal.pk, action="release", key="blocked")


def test_multiple_complaints_and_final_review_hold(closed):
    buyer, agent, manager, deal = closed
    finish(closed)
    first = lodge(values=inputs(deal_id=str(deal.pk)))
    second = lodge(values=inputs(deal_id=str(deal.pk)))
    assert Payout.objects.get(deal=deal).status == "ON_HOLD"
    first = move(manager, first, "IN_REVIEW")
    first = move(manager, first, "RESOLVED", "Outcome")
    assert PayoutBlock.objects.filter(deal=deal, is_open=True).count() == 1
    with pytest.raises(ValidationError):
        payout_action(actor=manager, deal_id=deal.pk, action="release", key="second-open")
    request_final_review(complaint_id=first.pk, token=token_for(first), reason="Disagree")
    assert PayoutBlock.objects.filter(deal=deal, is_open=True).count() == 2
