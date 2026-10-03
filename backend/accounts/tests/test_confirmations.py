from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.confirmations import consume_confirmation, issue_confirmation
from accounts.models import User


@pytest.mark.django_db
def test_confirmation_token_is_hashed_bound_and_single_use():
    user = User.objects.create_user(email="asha@example.test", phone="+255700123456", full_name="Asha", password="Strong-pass-482!")
    confirmation, token = issue_confirmation(user=user, purpose="owner_price_confirmation", subject_type="listing", subject_id="abc")
    assert confirmation.token_digest != token
    assert consume_confirmation(confirmation_id=confirmation.pk, raw_token="wrong", user=user, purpose="owner_price_confirmation") is False
    assert consume_confirmation(confirmation_id=confirmation.pk, raw_token=token, user=user, purpose="owner_price_confirmation") is True
    assert consume_confirmation(confirmation_id=confirmation.pk, raw_token=token, user=user, purpose="owner_price_confirmation") is False


@pytest.mark.django_db
def test_expired_confirmation_is_rejected():
    user = User.objects.create_user(email="asha@example.test", phone="+255700123456", full_name="Asha", password="Strong-pass-482!")
    confirmation, token = issue_confirmation(user=user, purpose="full_check_consent", lifetime=timedelta(seconds=-1))
    assert consume_confirmation(confirmation_id=confirmation.pk, raw_token=token, user=user, purpose="full_check_consent") is False
    assert confirmation.expires_at < timezone.now()
