from datetime import timedelta
from unittest.mock import patch
import pytest
from django.core import mail
from django.test import override_settings
from django.db import connection, transaction, DatabaseError
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.professionals.tests.test_professionals import account
from apps.listings.tests.test_services import create_listing_for
from apps.marketing import services
from apps.marketing.models import CampaignDelivery, Content, FeaturedListing, MarketingConsent, ConsentHistory, CampaignAttempt
from apps.payments.idempotency import Conflict

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def public_url():
    with override_settings(MARKETPLACE_PUBLIC_URL="https://example.test"):
        yield


def campaign_values():
    return dict(subject_en="Market news", subject_sw="Habari za soko", body_en="Latest properties", body_sw="Mali mpya", target_path="/", source_tag="spring-launch")


def period():
    now = timezone.now()
    return dict(starts_at=now - timedelta(hours=1), ends_at=now + timedelta(days=1), enabled=True)


@pytest.mark.parametrize("role", ["buyer", "owner", "agent", "local_official", "professional", "verifier"])
def test_marketing_staff_access_denies_other_roles(role):
    client = APIClient()
    client.force_authenticate(account(role))
    for route in ["content", "featured", "campaigns"]:
        assert client.get(f"/api/v1/marketing/staff/{route}/").status_code == 403


@pytest.mark.parametrize("role", ["marketer", "management"])
def test_authorized_staff_content_featured_dates_and_languages(role):
    actor, owner = account(role), account("owner")
    listing = create_listing_for(owner, status="ACTIVE")
    values = dict(slug="guide", kind="BANNER", title_en="Guide", title_sw="Mwongozo", body_en="Read the guide", body_sw="Soma mwongozo", target_path="/", source_tag="guide-banner", **period())
    row = services.save_item(actor=actor, model=Content, values=values.copy())
    feature = services.save_item(actor=actor, model=FeaturedListing, values=dict(listing_id=listing.listing_id, **period()))
    client = APIClient()
    payload = client.get("/api/v1/marketing/").data
    assert payload["content"][0]["title"] == "Mwongozo"
    assert "source_tag=guide-banner" in payload["content"][0]["link"]
    assert payload["featured"][0]["listing_id"] == listing.listing_id
    assert client.get("/api/v1/marketing/?language=en").data["content"][0]["title"] == "Guide"
    with pytest.raises(Conflict):
        services.save_item(actor=actor, model=Content, item_id=row.pk, version=0, values=values.copy())
    feature.ends_at = timezone.now() - timedelta(minutes=1)
    feature.save()
    assert client.get("/api/v1/marketing/").data["featured"] == []
    listing.status = "SUSPENDED"
    listing.save()
    with pytest.raises(Exception) as exc:
        services.save_item(actor=actor, model=FeaturedListing, values=dict(listing_id=listing.listing_id, **period()))
    assert getattr(exc.value, "status_code", None) == 404


def test_consent_defaults_withdrawal_and_campaign_results(mailoutbox):
    staff, consenting, withdrawn, never = account("marketer"), account("buyer"), account("buyer"), account("buyer")
    for user in [consenting, withdrawn]:
        services.consent(actor=user, agreed=True, version=0, policy_version="2026-10")
    campaign = services.create_campaign(actor=staff, values=campaign_values())
    assert campaign.deliveries.count() == 2
    services.consent(actor=withdrawn, agreed=False, version=1, policy_version="2026-10")
    cancelled = services.deliver(campaign.deliveries.get(recipient=withdrawn).pk)
    assert cancelled.status == "CANCELLED" and not mailoutbox
    sent = services.deliver(campaign.deliveries.get(recipient=consenting).pk)
    assert sent.status == "SENT" and len(mailoutbox) == 1
    services.deliver(sent.pk)
    assert len(mailoutbox) == 1
    assert services.click(services.delivery_token(sent)).endswith("/?source_tag=spring-launch")
    services.click(services.delivery_token(sent))
    result = services.results(staff)[0]
    assert result["sent"] == 1 and result["cancelled"] == 1 and result["clicks"] == 1
    for secret in [consenting.email, consenting.full_name, consenting.phone, str(never.pk)]:
        assert secret not in str(result)
    assert ConsentHistory.objects.count() == 3


def test_delivery_failure_redacted_and_retry_bounded():
    staff, user = account("management"), account("buyer")
    services.consent(actor=user, agreed=True, version=0, policy_version="v1")
    campaign = services.create_campaign(actor=staff, values=campaign_values())
    delivery = campaign.deliveries.get()
    with patch("apps.notifications.services.EmailMessage.send", side_effect=RuntimeError("secret-password")):
        for _ in range(5):
            CampaignDelivery.objects.filter(pk=delivery.pk).update(next_attempt_at=None)
            delivery = services.deliver(delivery.pk)
    assert delivery.status == "FAILED" and delivery.attempts == 5
    assert CampaignAttempt.objects.count() == 5
    assert "secret-password" not in str(list(CampaignAttempt.objects.values()))


@pytest.mark.parametrize("path", ["https://evil.test/", "//evil.test/", "/\\evil", "/?next=evil", "/#evil", "/\r\nInjected"])
def test_campaign_links_reject_open_redirects(path):
    with pytest.raises(ValidationError):
        services.tagged_link(path, "valid-source")


def test_persisted_permissions_and_audit_rollback():
    actor = account("marketer")
    with patch("apps.marketing.services.create_audit_log", side_effect=RuntimeError("audit")), pytest.raises(RuntimeError):
        services.create_campaign(actor=actor, values=campaign_values())
    assert not CampaignDelivery.objects.exists()
    User.objects.filter(pk=actor.pk).update(is_active=False)
    with pytest.raises(PermissionDenied):
        services.create_campaign(actor=actor, values=campaign_values())


def test_consent_api_blocks_overposting_and_checks_version():
    user = account("buyer")
    client = APIClient()
    client.force_authenticate(user)
    path = "/api/v1/marketing/consent/"
    assert client.get(path).data == {"agreed": False, "version": 0}
    data = {"agreed": True, "version": 0, "policy_version": "v1"}
    assert client.put(path, {**data, "user": str(account("buyer").pk)}, format="json").status_code == 400
    assert client.put(path, data, format="json").status_code == 200
    assert client.put(path, data, format="json").status_code == 409


def test_database_history_guards():
    user = account("buyer")
    services.consent(actor=user, agreed=True, version=0, policy_version="v1")
    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM marketing_consenthistory")


def test_click_invalid_or_unsent_link_denied():
    client = APIClient()
    assert client.get("/api/v1/marketing/click/?token=invalid").status_code == 400
    staff, user = account("marketer"), account("buyer")
    services.consent(actor=user, agreed=True, version=0, policy_version="v1")
    delivery = services.create_campaign(actor=staff, values=campaign_values()).deliveries.get()
    assert client.get("/api/v1/marketing/click/", {"token": services.delivery_token(delivery)}).status_code == 404


@pytest.mark.django_db(transaction=True)
def test_concurrent_consent_first_write_has_one_winner():
    from apps.payments.tests.test_concurrency import concurrent
    user = account("buyer")
    def mutate():
        try:
            services.consent(actor=user, agreed=True, version=0, policy_version="v1")
            return "OK"
        except Conflict:
            return "STALE"
    assert sorted(concurrent(mutate)) == ["OK", "STALE"]
    assert ConsentHistory.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_campaign_workers_submit_once():
    from apps.payments.tests.test_concurrency import concurrent
    user, staff = account("buyer"), account("marketer")
    services.consent(actor=user, agreed=True, version=0, policy_version="v1")
    delivery = services.create_campaign(actor=staff, values=campaign_values()).deliveries.get()
    with patch("apps.notifications.services.SMTPAdapter.deliver_message") as send:
        assert concurrent(lambda: services.deliver(delivery.pk).status) == ("SENT", "SENT")
    assert send.call_count == 1 and CampaignAttempt.objects.count() == 1


def test_staff_lists_show_featured_cards_and_campaign_subjects():
    actor, owner = account("marketer"), account("owner")
    listing = create_listing_for(owner, status="ACTIVE")
    services.save_item(actor=actor, model=FeaturedListing, values=dict(listing_id=listing.listing_id, **period()))
    client = APIClient()
    client.force_authenticate(actor)
    featured = client.get("/api/v1/marketing/staff/featured/").data
    assert featured[0]["listing_id"] == listing.listing_id
    assert featured[0]["category"] == listing.property.category
    assert "lister" not in str(featured) and "phone" not in str(featured)
    services.create_campaign(actor=actor, values=dict(subject_en="Homes", subject_sw="Nyumba", body_en="See homes", body_sw="Ona nyumba", target_path="/listings", source_tag="homes-oct"))
    campaigns = client.get("/api/v1/marketing/staff/campaigns/").data
    assert campaigns[0]["subject_sw"] == "Nyumba" and campaigns[0]["target_path"] == "/listings"
