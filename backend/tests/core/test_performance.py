from time import monotonic
import uuid
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from apps.professionals.tests.test_professionals import account
from apps.listings.tests.test_services import create_listing_for
from apps.listings.models import Listing
from apps.analytics.models import MarketAggregate, AggregateRun

pytestmark = pytest.mark.django_db


def test_server_search_detail_and_precomputed_panel_budgets():
    owner, marketer = account("owner"), account("marketer")
    first = create_listing_for(owner, status="ACTIVE")
    Listing.objects.bulk_create([Listing(listing_id="BENCH-" + uuid.uuid4().hex, property=first.property, lister=owner, lister_kind="OWNER", selling_price=100000000, owner_price=100000000, status="ACTIVE") for _ in range(499)])
    MarketAggregate.objects.bulk_create([MarketAggregate(day=timezone.localdate(), kind="ACTIVITY", area_key=str(index), region=first.property.region_id, district=first.property.district_id, ward=first.property.ward_id, category="LAND", metrics={"enquiries": index, "views": index * 2}) for index in range(1000)])
    AggregateRun.objects.create(completed_at=timezone.now(), cells=1000)
    client = APIClient()
    measurements = {}
    for name, path, budget in [("search", "/api/v1/public/listings/", 2), ("detail", f"/api/v1/public/listings/{first.listing_id}/", 3), ("panel", "/api/v1/analytics/", 5)]:
        if name == "panel":
            client.force_authenticate(marketer)
        start = monotonic()
        with CaptureQueriesContext(connection) as queries:
            result = client.get(path)
        elapsed = monotonic() - start
        assert result.status_code == 200
        assert elapsed < budget, f"{name} exceeded local server budget: {elapsed}"
        assert len(queries) <= (15 if name == "panel" else 5)
        measurements[name] = {"seconds": round(elapsed, 4), "queries": len(queries)}
    print("Local server benchmark (no mobile/network claim):", measurements)
