from decimal import Decimal

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.administration import examples
from apps.audit.models import AuditLog
from apps.commissions.models import RateTable
from apps.listings.tests.test_services import create_listing_for
from apps.localities.models import Locality
from apps.professionals.tests.test_professionals import account
from apps.properties.models import PropertyRecord
from apps.verification.configuration import setting

pytestmark = pytest.mark.django_db


def client(user):
    api = APIClient()
    api.force_authenticate(user)
    return api


def test_seed_example_values_once_and_leaves_existing_values_alone():
    """D5: the example commission table and full check fee, created only where nothing exists."""
    call_command("seed_example_values")
    table = RateTable.objects.get()
    assert table.published_at and table.version == 1
    assert [(band.lower, band.upper, band.oweru_rate, band.agent_rate) for band in table.bands.order_by("lower")] == list(examples.RATE_BANDS)
    assert Decimal(str(setting("full_check_fee"))) == examples.FULL_CHECK_FEE
    call_command("seed_example_values")
    assert RateTable.objects.count() == 1


def test_seed_keeps_a_different_published_table_and_adds_the_example_as_draft():
    manager = account("management")
    other = RateTable.objects.create(version=1)
    other.bands.create(lower=0, upper=None, oweru_rate=Decimal("0.05"), agent_rate=Decimal("0.05"))
    RateTable.objects.filter(pk=other.pk).update(published_at="2026-01-01T00:00:00Z")
    call_command("seed_example_values")
    versions = client(manager).get("/api/v1/commissions/rate-tables/versions/").data
    assert [(row["version"], row["current"], row["published_at"] is None) for row in versions] == [(2, False, True), (1, True, False)]


def test_pending_street_merges_into_approved_one_and_moves_its_properties():
    """LST-03, ADM-03: a mistyped street is folded into the approved one, never deleted."""
    manager, owner = account("management"), account("owner")
    listing = create_listing_for(owner, lister_kind="OWNER", status="ACTIVE")
    record = listing.property
    approved = record.locality
    Locality.objects.filter(pk=approved.pk).update(approved=True)
    typed = Locality.objects.create(ward=approved.ward, name=approved.name + " B", kind=approved.kind, approved=False)
    PropertyRecord.objects.filter(pk=record.pk).update(locality=typed)
    api = client(manager)

    pending = api.get("/api/v1/localities/review-queue/").data
    row = next(item for item in pending if item["id"] == str(typed.pk))
    assert row["properties"] == 1 and str(approved.pk) in {item["id"] for item in row["approved_in_ward"]}
    assert api.post(f"/api/v1/localities/{typed.pk}/merge/", {"into": str(typed.pk)}, format="json").status_code == 400
    merged = api.post(f"/api/v1/localities/{typed.pk}/merge/", {"into": str(approved.pk)}, format="json")
    assert merged.status_code == 200 and merged.data["properties_moved"] == 1, merged.data
    record.refresh_from_db()
    typed.refresh_from_db()
    assert record.locality_id == approved.pk and typed.merged_into_id == approved.pk
    assert str(typed.pk) not in {item["id"] for item in api.get("/api/v1/localities/review-queue/").data}
    assert client(owner).get("/api/v1/localities/review-queue/").status_code == 403


def test_audit_log_filters_by_action_person_and_pages():
    """ADM-04."""
    manager, other = account("management"), account("management")
    for number in range(55):
        AuditLog.objects.create(actor=other, action="listing.suspended", entity_type="Listing", entity_id=f"L-{number}")
    AuditLog.objects.create(actor=manager, action="rate_table.published", entity_type="RateTable", entity_id="T-1")
    api = client(manager)
    first = api.get("/api/v1/management/audit/?action=listing").data
    assert len(first["results"]) == 50 and first["has_next"] and first["results"][0]["actor"] == other.full_name
    assert len(api.get("/api/v1/management/audit/?action=listing&page=2").data["results"]) == 5
    mine = api.get(f"/api/v1/management/audit/?actor={manager.pk}&action=rate_table").data["results"]
    assert [row["entity_id"] for row in mine] == ["T-1"]
    assert "listing" in first["groups"] and "rate_table" in first["groups"]


def test_message_templates_list_titles_defaults_and_history():
    """NTF-04."""
    manager = account("management")
    api = client(manager)
    rows = api.get("/api/v1/management/notifications/message-templates/").data
    row = next(item for item in rows if item["key"] == "OFFICIAL_REGISTRATION")
    assert row["title"]["sw"] and row["history"] == []
    text = "Oweru: jisajili {reference}. {link}"
    saved = api.put("/api/v1/management/notifications/message-templates/OFFICIAL_REGISTRATION/", {"en": "Oweru: register {reference}. {link}", "sw": text, "version": 0}, format="json")
    assert saved.status_code == 200, saved.data
    row = next(item for item in api.get("/api/v1/management/notifications/message-templates/").data if item["key"] == "OFFICIAL_REGISTRATION")
    assert row["sw"] == text and row["history"][0]["actor"] == manager.full_name


def test_listing_lookup_returns_the_version_needed_to_suspend():
    """LST-12."""
    manager, owner = account("management"), account("owner")
    listing = create_listing_for(owner, lister_kind="OWNER", status="ACTIVE")
    api = client(manager)
    found = api.get(f"/api/v1/management/listing-actions/{listing.listing_id}/").data
    assert found["status"] == "ACTIVE" and found["lister"] == owner.full_name
    done = api.post(f"/api/v1/management/listing-actions/{listing.listing_id}/", {"version": found["version"], "reason": "Fake photos", "action": "suspend"}, format="json")
    assert done.status_code == 200 and done.data["status"] == "SUSPENDED"
    assert client(owner).get(f"/api/v1/management/listing-actions/{listing.listing_id}/").status_code == 403


def test_oweru_bank_account_is_readable_by_management_only():
    from apps.payments.models import BankAccount
    manager, buyer = account("management"), account("buyer")
    assert client(manager).get("/api/v1/management/finance/oweru-bank/").data is None
    BankAccount.objects.create(is_oweru=True, bank_name="CRDB", account_name="Oweru Ltd", account_number="0150123456", branch="Posta")
    assert client(manager).get("/api/v1/management/finance/oweru-bank/").data["bank_name"] == "CRDB"
    assert client(buyer).get("/api/v1/management/finance/oweru-bank/").status_code == 403
