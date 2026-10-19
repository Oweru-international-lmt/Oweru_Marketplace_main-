from io import BytesIO
from zipfile import ZipFile
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
import pytest
from django.db import connection, transaction, DatabaseError
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from apps.audit.services import create_audit_log
from apps.professionals.tests.test_professionals import account
from apps.listings.tests.test_services import create_listing_for
from apps.leads.services import create_lead, LeadTransitionService
from apps.analytics.models import MarketEvent, MarketAggregate, LeadAttribution
from apps.analytics.services import refresh, record_search, record_view, sqm
from apps.analytics.export import workbook

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("role", ["buyer", "owner", "agent", "verifier", "local_official", "professional"])
def test_analytics_requires_active_staff_permissions(role):
    client = APIClient()
    client.force_authenticate(account(role))
    assert client.get("/api/v1/analytics/").status_code == 403
    assert client.get("/api/v1/analytics/export/").status_code == 403


@pytest.mark.parametrize("role", ["management", "marketer"])
def test_empty_panel_staleness_and_xlsx_export(role):
    client = APIClient()
    client.force_authenticate(account(role))
    payload = client.get("/api/v1/analytics/")
    assert payload.status_code == 200 and payload.data["rows"] == [] and payload.data["stale"]
    refresh()
    assert not client.get("/api/v1/analytics/").data["stale"]
    response = client.get("/api/v1/analytics/export/")
    assert response.status_code == 200
    assert "spreadsheetml" in response["Content-Type"]
    with ZipFile(BytesIO(response.content)) as archive:
        assert "xl/worksheets/sheet1.xml" in archive.namelist()


def test_search_view_durable_privacy_and_source_buckets():
    listing = create_listing_for(account("owner"), status="ACTIVE")
    record_search({"category": "LAND", "region": str(listing.property.region_id), "min_price": "20", "source_tag": "newsletter"})
    record_view(listing, "newsletter")
    assert MarketEvent.objects.count() == 2
    fields = {field.name for field in MarketEvent._meta.fields}
    assert not fields & {"buyer", "owner", "phone", "email", "ip_address", "listing", "pin", "user_agent"}
    assert MarketEvent.objects.get(kind="SEARCH").filters == ["category", "min_price", "region"]
    assert MarketEvent.objects.get(kind="VIEW").source_tag == "newsletter"


def test_market_snapshot_stock_prices_units_cohort_response_and_filters():
    owner, buyer, marketer = account("owner"), account("buyer"), account("marketer")
    listing = create_listing_for(owner, status="ACTIVE")
    listing.property.size_unit = "acre"
    listing.property.stated_size = Decimal("1")
    listing.property.save()
    create_audit_log(actor=owner, action="listing.activated", entity_type="Listing", entity_id=listing.pk)
    lead = create_lead(actor=buyer, listing_id=listing.listing_id, source="ENQUIRY", source_tag="spring")
    assert LeadAttribution.objects.get(lead=lead).source_tag == "spring"
    LeadTransitionService.transition(actor=owner, lead_id=lead.pk, stage="CONTACTED")
    LeadTransitionService.transition(actor=owner, lead_id=lead.pk, stage="VIEWING")
    record_view(listing, "spring")
    refresh()
    client = APIClient()
    client.force_authenticate(marketer)
    result = client.get("/api/v1/analytics/", {"region": str(listing.property.region_id), "category": "LAND"})
    assert result.status_code == 200
    stock = next(row["metrics"] for row in result.data["rows"] if row["kind"] == "STOCK")
    assert stock["active_listings"] == 1
    assert stock["verification_share"] == {"0": 1}
    assert "_selling_samples" not in stock
    assert stock["selling_price"]["median"] == float(listing.selling_price)
    assert stock["price_per_sqm"]["average"] == pytest.approx(float(listing.selling_price / Decimal("4046.8564224")))
    activity = next(row["metrics"] for row in result.data["rows"] if row["kind"] == "ACTIVITY")
    assert activity["enquiries"] == 1 and activity["views"] == 1
    assert activity["new_listers"] == 1 and activity["listings_created"] == 1
    assert activity["conversion"]["NEW_to_VIEWING"] == 1
    assert activity["average_response_seconds"] is not None
    assert activity["sources_enquiry"] == {"spring": 1}
    assert activity["average_time_to_first_enquiry_days"] is not None
    for secret in [buyer.email, buyer.phone, buyer.full_name, str(buyer.pk), owner.email, owner.phone]:
        assert secret not in repr(result.data)
    assert client.get("/api/v1/analytics/", {"category": "HOUSE"}).data["rows"] == []
    monthly = client.get("/api/v1/analytics/", {"kind": "MONTHLY", "start": timezone.localdate().isoformat(), "end": timezone.localdate().isoformat()}).data["rows"]
    assert monthly[0]["metrics"]["observed_days"] == 1
    assert monthly[0]["metrics"]["selling_price"]["median"] == float(listing.selling_price)
    with CaptureQueriesContext(connection) as queries:
        assert client.get("/api/v1/analytics/").status_code == 200
    assert len(queries) < 15


def test_snapshot_refresh_idempotent_no_fabricated_stock_history():
    create_listing_for(account("owner"), status="ACTIVE")
    refresh()
    count = MarketAggregate.objects.count()
    refresh()
    assert MarketAggregate.objects.count() == count
    assert MarketAggregate.objects.filter(kind="STOCK").get().day == timezone.localdate()


@pytest.mark.parametrize("query", [{"start": "2026-10-12", "end": "2026-10-11"}, {"start": "2020-01-01", "end": "2026-01-01"}, {"region": "not-a-uuid"}, {"owner_price": "1"}])
def test_invalid_panel_filters_rejected(query):
    client = APIClient()
    client.force_authenticate(account("marketer"))
    assert client.get("/api/v1/analytics/", query).status_code == 400


def test_export_strings_are_never_formulas():
    data = workbook([{"day": timezone.localdate(), "kind": "ACTIVITY", "category": "=CMD()", "metrics": {"source": "=HYPERLINK(\"evil\")"}}])
    with ZipFile(BytesIO(data)) as archive:
        xml = archive.read("xl/worksheets/sheet1.xml").decode()
    assert "<f>" not in xml and 't="inlineStr"' in xml and "=HYPERLINK" in xml


def test_database_events_immutable_and_fail_open_public_browsing():
    listing = create_listing_for(account("owner"), status="ACTIVE")
    record_view(listing)
    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM analytics_marketevent")
    with patch("apps.analytics.services.record_view", side_effect=RuntimeError("unavailable")):
        assert APIClient().get(f"/api/v1/public/listings/{listing.listing_id}/").status_code == 200


def test_unknown_area_is_not_assigned_from_raw_coordinates():
    record_search({})
    refresh()
    row = MarketAggregate.objects.get(kind="ACTIVITY")
    assert row.region is None and row.district is None and row.category == ""
    assert row.metrics["searches"] == 1


def test_panel_names_the_areas_of_its_cells():
    client = APIClient()
    client.force_authenticate(account("management"))
    payload = client.get("/api/v1/analytics/").data
    assert payload["areas"] == {}
    for row in payload["rows"]:
        assert row["region"] is None or str(row["region"]) in payload["areas"]
