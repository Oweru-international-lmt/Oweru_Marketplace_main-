from datetime import timedelta
from unittest.mock import patch, MagicMock
import pytest
from django.utils import timezone
from django.core.management import call_command
from rest_framework.exceptions import ValidationError, PermissionDenied
from apps.listings.tests.test_services import create_user, grant_role
from apps.listings.tests.test_api import client_for
from apps.lister_identity.models import ListerIdentity
from apps.roles.legacy_authorization.models import UserRole
from apps.payments.onboarding import enable_lister_actions
from apps.payments.models import FinancialNotice, ConfirmationDelivery
from apps.payments.confirmations import request_confirmation, mark_sent, decide
from apps.media.storage import get_private_media_storage
from .conftest import bank_values

pytestmark = pytest.mark.django_db


def test_explicit_lister_permission_onboarding(workflow):
    buyer, _, manager, _, _, _ = workflow
    grant_role(buyer, "agent")
    with pytest.raises(ValidationError):
        enable_lister_actions(actor=manager, user_id=buyer.pk, role_code="agent")
    ListerIdentity.objects.create(user=buyer, national_id_number="TEST-ID", national_id_photo_ref="test-id", live_selfie_ref="test-selfie", status="APPROVED", reviewed_at=timezone.now(), reviewed_by=manager, expires_at=timezone.now()+timedelta(days=30))
    assert not buyer.has_marketplace_permission("lead.update")
    assignment = enable_lister_actions(actor=manager, user_id=buyer.pk, role_code="agent")
    assert buyer.has_marketplace_permission("lead.update")
    assert enable_lister_actions(actor=manager, user_id=buyer.pk, role_code="agent").pk == assignment.pk
    call_command('enable_marketplace_lister_actions', manager_id=str(manager.pk), lister_id=str(buyer.pk), role="agent")
    assert UserRole.objects.filter(user=buyer, role__code="agent").count() == 1
    with pytest.raises(PermissionDenied):
        enable_lister_actions(actor=buyer, user_id=buyer.pk, role_code="agent")


def test_notice_intents_and_manual_send(closed):
    _, agent, manager, deal = closed
    assert FinancialNotice.objects.filter(lead=deal.lead, purpose="LEAD_CREATED").count() == 1
    assert FinancialNotice.objects.filter(deal=deal).count() == 2
    manager_client = client_for(manager)
    response = manager_client.get('/api/v1/management/finance/notices/')
    assert response.status_code == 200 and len(response.data) == 3
    notice = FinancialNotice.objects.filter(deal=deal).first()
    url = f'/api/v1/management/finance/notices/{notice.pk}/sent/'
    assert manager_client.post(url, {}).status_code == 200
    assert manager_client.post(url, {}).status_code == 200
    assert client_for(agent).get('/api/v1/management/finance/notices/').status_code == 403


def test_rate_draft_api_and_immutable_publish(workflow):
    _, agent, manager, _, _, _ = workflow
    client = client_for(manager)
    payload = {"version": 2, "total_rate": "0.10", "bands": [{"lower": "0", "upper": None, "oweru_rate": "0.03", "agent_rate": "0.07"}]}
    response = client.post('/api/v1/commissions/rate-tables/', payload, format="json")
    assert response.status_code == 201
    pk = response.data["id"]
    assert client_for(agent).get(f'/api/v1/commissions/rate-tables/{pk}/').status_code == 403
    payload["bands"][0]["oweru_rate"] = "0.04"
    payload["bands"][0]["agent_rate"] = "0.06"
    assert client.put(f'/api/v1/commissions/rate-tables/{pk}/', payload, format="json").status_code == 200
    assert client.post(f'/api/v1/commissions/rate-tables/{pk}/publish/', {}).status_code == 200
    assert client.put(f'/api/v1/commissions/rate-tables/{pk}/', payload, format="json").status_code == 400
    assert client_for(agent).get(f'/api/v1/commissions/rate-tables/{pk}/').status_code == 200


def test_expired_and_changed_owner_context(workflow):
    _, agent, manager, listing, _, _ = workflow
    response = request_confirmation(actor=agent, purpose="OWNER_PRICE", listing_id=listing.listing_id, owner_name="External Owner", owner_whatsapp="+255799000009")
    delivery = ConfirmationDelivery.objects.get(pk=response["delivery_id"])
    token = delivery.delivery_token
    mark_sent(actor=manager, delivery_id=delivery.pk)
    type(listing).objects.filter(pk=listing.pk).update(owner_price=99000000)
    with pytest.raises(ValidationError):
        decide(delivery_id=delivery.pk, token=token, decision="CONFIRM", bank=bank_values(), key="owner")
    delivery.expires_at = timezone.now()-timedelta(seconds=1); delivery.save()
    with pytest.raises(PermissionDenied):
        decide(delivery_id=delivery.pk, token=token, decision="CONFIRM", bank=bank_values(), key="owner")


def test_s3_adapter_uses_private_object_and_signed_url(settings):
    from io import BytesIO
    settings.MEDIA_STORAGE_BACKEND = "s3"
    settings.MEDIA_STORAGE_BUCKET = "private-test-bucket"
    settings.MEDIA_STORAGE_ENDPOINT = "https://storage.example.test"
    client = MagicMock()
    client.generate_presigned_url.return_value = "https://storage.example.test/signed"
    with patch('boto3.client', return_value=client):
        storage = get_private_media_storage()
        assert storage.save_private_object(key="private/test", content=BytesIO(b"test"), content_type="application/pdf") == "private/test"
        assert storage.generate_signed_read_url(key="private/test", expires_in=60).endswith("signed")
        assert "ACL" not in client.put_object.call_args.kwargs
        assert client.generate_presigned_url.call_args.kwargs["ExpiresIn"] == 60
