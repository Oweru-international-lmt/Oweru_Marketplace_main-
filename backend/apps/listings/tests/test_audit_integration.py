from decimal import Decimal
import uuid

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient, APIRequestFactory

from apps.audit.models import AuditLog
from apps.listings.admin import ListingAdmin
from apps.listings.audit_events import (
    LISTING_ACTIVATED,
    LISTING_CREATED,
    LISTING_RESTORED,
    LISTING_SUSPENDED,
    LISTING_UPDATED,
    LISTING_WITHDRAWN,
)
from apps.listings.models import Listing
from apps.listings.services import (
    activate_listing,
    create_listing,
    restore_listing,
    suspend_listing,
    update_listing,
    withdraw_listing,
)
from apps.localities.models import District, Locality, Region, Ward
from apps.properties.models import PropertyRecord
from apps.roles.catalog import ROLE_AGENT, ROLE_BUYER, ROLE_MANAGEMENT, ROLE_OWNER
from apps.roles.models import Role, UserRole
from apps.roles.services import bootstrap_canonical_roles


pytestmark = pytest.mark.django_db

SENSITIVE_MARKERS = (
    "password",
    "password_hash",
    "access token",
    "refresh token",
    "jwt",
    "secret",
    "national_id",
    "national_id_number",
    "national_id_photo_ref",
    "live_selfie_ref",
    "owner_whatsapp",
    "owner_bank",
    "email",
    "phone",
    "pin",
    "boundary",
    "latitude",
    "longitude",
    "coordinates",
    "road access",
    "quiet plot",
    "sensitive internal investigation",
    "100000000",
    "120000000",
)


def create_user(email=None, *, is_active=True):
    email = email or f"listing-audit-{uuid.uuid4().hex[:10]}@example.test"
    return get_user_model().objects.create_user(
        email=email,
        phone=f"+2557{abs(hash(email)) % 100000000:08d}",
        full_name="Listing Audit User",
        password="StrongPass123!",
        is_active=is_active,
    )


def grant_role(user, role_code, *, is_active=True, role_active=True):
    bootstrap_canonical_roles()
    role = Role.objects.get(code=role_code)
    role.is_active = role_active
    role.save(update_fields=["is_active"])
    return UserRole.objects.create(user=user, role=role, is_active=is_active)


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def create_hierarchy(prefix=None):
    prefix = prefix or f"ListingAudit{uuid.uuid4().hex[:8]}"
    region = Region.objects.create(name=f"{prefix} Region")
    district = District.objects.create(region=region, name=f"{prefix} District")
    ward = Ward.objects.create(district=district, name=f"{prefix} Ward")
    locality = Locality.objects.create(
        ward=ward,
        name=f"{prefix} Street",
        kind=Locality.Kind.STREET,
        approved=True,
    )
    return region, district, ward, locality


def create_property_record(*, created_by, prefix=None):
    prefix = prefix or f"ListingAuditProperty{uuid.uuid4().hex[:8]}"
    region, district, ward, locality = create_hierarchy(prefix)
    return PropertyRecord.objects.create(
        property_id=f"OWR-{uuid.uuid4().hex[:16].upper()}",
        category=PropertyRecord.Category.LAND,
        pin=Point(39.2083, -6.7924, srid=4326),
        boundary=None,
        region=region,
        district=district,
        ward=ward,
        locality=locality,
        stated_size=Decimal("1200.50"),
        size_unit="sqm",
        title_type=PropertyRecord.TitleType.UNKNOWN,
        created_by=created_by,
    )


def create_listing_direct(actor, *, status=Listing.Status.DRAFT, lister_kind=Listing.ListerKind.OWNER):
    property_record = create_property_record(created_by=actor)
    selling_price = Decimal("120000000") if lister_kind == Listing.ListerKind.AGENT else Decimal("100000000")
    return Listing.objects.create(
        listing_id=f"LST-{uuid.uuid4().hex[:16].upper()}",
        property=property_record,
        lister=actor,
        lister_kind=lister_kind,
        selling_price=selling_price,
        owner_price=Decimal("100000000"),
        currency=Listing.Currency.TZS,
        status=status,
        description="Quiet plot with road access",
        features=["road access", {"private": "content"}],
    )


def create_service_listing(actor):
    return create_listing(
        actor=actor,
        property_record=create_property_record(created_by=actor),
        lister_kind=Listing.ListerKind.OWNER,
        selling_price=Decimal("100000000"),
        owner_price=Decimal("100000000"),
        description="Quiet plot with road access",
        features=["road access", {"private": "content"}],
    )


def rendered_metadata(log):
    return (repr(log.before) + repr(log.after)).lower()


def assert_safe_listing_metadata(log):
    rendered = rendered_metadata(log)
    for marker in SENSITIVE_MARKERS:
        assert marker not in rendered


def latest(action):
    return AuditLog.objects.filter(action=action).latest("created_at")


def test_listing_created_audit_success_is_safe_and_single_event():
    actor = create_user("listing-created-audit@example.test")
    grant_role(actor, ROLE_OWNER)

    listing = create_service_listing(actor)

    logs = AuditLog.objects.filter(action=LISTING_CREATED)
    assert logs.count() == 1
    log = logs.get()
    assert log.actor == actor
    assert log.entity_type == "Listing"
    assert log.entity_id == str(listing.pk)
    assert log.after == {
        "listing_id": listing.listing_id,
        "property_id": listing.property.property_id,
        "lister_kind": Listing.ListerKind.OWNER,
        "status": Listing.Status.DRAFT,
    }
    assert_safe_listing_metadata(log)


def test_listing_updated_audit_records_changed_field_names_only_and_noop_is_quiet():
    actor = create_user("listing-updated-audit@example.test")
    grant_role(actor, ROLE_OWNER)
    listing = create_service_listing(actor)
    before = AuditLog.objects.filter(action=LISTING_UPDATED).count()

    update_listing(actor=actor, listing=listing, selling_price=Decimal("110000000"), owner_price=Decimal("110000000"), description="Quiet plot updated")
    log = latest(LISTING_UPDATED)
    assert AuditLog.objects.filter(action=LISTING_UPDATED).count() == before + 1
    assert log.actor == actor
    assert log.after == {
        "listing_id": listing.listing_id,
        "changed_fields": ["description", "owner_price", "selling_price"],
    }
    assert_safe_listing_metadata(log)

    before_noop = AuditLog.objects.filter(action=LISTING_UPDATED).count()
    listing.refresh_from_db()
    update_listing(actor=actor, listing=listing, description=listing.description)
    assert AuditLog.objects.filter(action=LISTING_UPDATED).count() == before_noop


def test_failed_create_update_and_activation_do_not_create_success_audit():
    buyer = create_user("listing-failed-buyer@example.test")
    owner = create_user("listing-failed-owner@example.test")
    other = create_user("listing-failed-other@example.test")
    grant_role(buyer, ROLE_BUYER)
    grant_role(owner, ROLE_OWNER)
    grant_role(other, ROLE_OWNER)
    listing = create_service_listing(owner)

    with pytest.raises(PermissionDenied):
        create_listing(
            actor=buyer,
            property_record=create_property_record(created_by=buyer),
            lister_kind=Listing.ListerKind.OWNER,
            selling_price=Decimal("100000000"),
            owner_price=Decimal("100000000"),
        )
    with pytest.raises(ValidationError):
        create_listing(
            actor=owner,
            property_record=create_property_record(created_by=owner),
            lister_kind=Listing.ListerKind.OWNER,
            selling_price=Decimal("0"),
            owner_price=Decimal("0"),
        )
    with pytest.raises(PermissionDenied):
        update_listing(actor=other, listing=listing, description="Denied")
    Listing.objects.filter(pk=listing.pk).update(status=Listing.Status.ACTIVE)
    with pytest.raises(PermissionDenied):
        update_listing(actor=owner, listing=listing, description="Denied")
    Listing.objects.filter(pk=listing.pk).update(status=Listing.Status.DRAFT)
    with pytest.raises(PermissionDenied):
        activate_listing(actor=other, listing=listing)
    with pytest.raises(ValidationError):
        activate_listing(actor=owner, listing=listing)

    assert AuditLog.objects.filter(action=LISTING_CREATED).count() == 1
    assert not AuditLog.objects.filter(action=LISTING_UPDATED).exists()
    assert not AuditLog.objects.filter(action=LISTING_ACTIVATED).exists()


def test_withdraw_audit_success_duplicate_invalid_attempt_and_rollback(monkeypatch):
    actor = create_user("listing-withdraw-audit@example.test")
    grant_role(actor, ROLE_OWNER)
    listing = create_listing_direct(actor, status=Listing.Status.ACTIVE)

    withdrawn = withdraw_listing(actor=actor, listing=listing)

    log = AuditLog.objects.get(action=LISTING_WITHDRAWN)
    assert withdrawn.status == Listing.Status.WITHDRAWN
    assert log.actor == actor
    assert log.after == {
        "listing_id": listing.listing_id,
        "from_status": Listing.Status.ACTIVE,
        "to_status": Listing.Status.WITHDRAWN,
    }
    assert_safe_listing_metadata(log)

    with pytest.raises(ValidationError):
        withdraw_listing(actor=actor, listing=listing)
    assert AuditLog.objects.filter(action=LISTING_WITHDRAWN).count() == 1

    rollback = create_listing_direct(actor, status=Listing.Status.ACTIVE)

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr("apps.listings.services.create_audit_log", fail_audit)
    with pytest.raises(RuntimeError):
        withdraw_listing(actor=actor, listing=rollback)
    rollback.refresh_from_db()
    assert rollback.status == Listing.Status.ACTIVE


def test_suspend_audit_reason_privacy_invalid_attempts_and_rollback(monkeypatch):
    lister = create_user("listing-suspend-lister@example.test")
    manager = create_user("listing-suspend-manager@example.test")
    other = create_user("listing-suspend-other@example.test")
    grant_role(lister, ROLE_OWNER)
    grant_role(manager, ROLE_MANAGEMENT)
    grant_role(other, ROLE_OWNER)
    listing = create_listing_direct(lister, status=Listing.Status.ACTIVE)
    reason = "Sensitive internal investigation details about owner_price 100000000"

    suspended = suspend_listing(actor=manager, listing=listing, reason=reason)

    log = AuditLog.objects.get(action=LISTING_SUSPENDED)
    assert suspended.status == Listing.Status.SUSPENDED
    assert log.actor == manager
    assert log.after == {
        "listing_id": listing.listing_id,
        "from_status": Listing.Status.ACTIVE,
        "to_status": Listing.Status.SUSPENDED,
        "reason_present": True,
    }
    assert_safe_listing_metadata(log)

    with pytest.raises(PermissionDenied):
        suspend_listing(actor=other, listing=listing, reason="Denied")
    with pytest.raises(ValidationError):
        suspend_listing(actor=manager, listing=listing, reason="")
    with pytest.raises(ValidationError):
        suspend_listing(actor=manager, listing=listing, reason="Denied duplicate")
    assert AuditLog.objects.filter(action=LISTING_SUSPENDED).count() == 1

    rollback = create_listing_direct(lister, status=Listing.Status.ACTIVE)

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr("apps.listings.services.create_audit_log", fail_audit)
    with pytest.raises(RuntimeError):
        suspend_listing(actor=manager, listing=rollback, reason="Rollback reason")
    rollback.refresh_from_db()
    assert rollback.status == Listing.Status.ACTIVE


def test_failed_restore_and_activation_prerequisites_do_not_create_success_audit():
    lister = create_user("listing-restore-lister@example.test")
    manager = create_user("listing-restore-manager@example.test")
    other = create_user("listing-restore-other@example.test")
    grant_role(lister, ROLE_OWNER)
    grant_role(manager, ROLE_MANAGEMENT)
    grant_role(other, ROLE_AGENT)
    suspended = create_listing_direct(lister, status=Listing.Status.SUSPENDED)

    with pytest.raises(PermissionDenied):
        restore_listing(actor=other, listing=suspended)
    with pytest.raises(ValidationError):
        restore_listing(actor=manager, listing=suspended)

    suspended.refresh_from_db()
    assert suspended.status == Listing.Status.SUSPENDED
    assert not AuditLog.objects.filter(action=LISTING_RESTORED).exists()
    assert not AuditLog.objects.filter(action=LISTING_ACTIVATED).exists()


def test_create_and_update_audit_failure_rolls_back_mutation(monkeypatch):
    actor = create_user("listing-audit-rollback@example.test")
    grant_role(actor, ROLE_OWNER)

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr("apps.listings.services.create_audit_log", fail_audit)
    with pytest.raises(RuntimeError):
        create_listing(
            actor=actor,
            property_record=create_property_record(created_by=actor),
            lister_kind=Listing.ListerKind.OWNER,
            selling_price=Decimal("100000000"),
            owner_price=Decimal("100000000"),
        )
    assert not Listing.objects.exists()

    monkeypatch.undo()
    listing = create_service_listing(actor)
    original_description = listing.description
    monkeypatch.setattr("apps.listings.services.create_audit_log", fail_audit)
    with pytest.raises(RuntimeError):
        update_listing(actor=actor, listing=listing, description="Rollback description")
    listing.refresh_from_db()
    assert listing.description == original_description


def test_management_sensitive_detail_and_collection_audit_without_per_row_explosion():
    lister = create_user("listing-sensitive-lister@example.test")
    second = create_user("listing-sensitive-second@example.test")
    manager = create_user("listing-sensitive-manager@example.test")
    grant_role(lister, ROLE_OWNER)
    grant_role(second, ROLE_OWNER)
    grant_role(manager, ROLE_MANAGEMENT)
    first_listing = create_listing_direct(lister)
    second_listing = create_listing_direct(second)

    collection_response = client_for(manager).get("/api/v1/listings/")
    detail_response = client_for(manager).get(f"/api/v1/listings/{first_listing.listing_id}/")

    assert collection_response.status_code == 200
    assert detail_response.status_code == 200
    logs = AuditLog.objects.filter(action="sensitive_data.accessed").order_by("created_at")
    assert logs.count() == 2
    collection_log, detail_log = logs
    assert collection_log.actor == manager
    assert collection_log.entity_type == "Listing"
    assert collection_log.entity_id == ""
    assert collection_log.after == {
        "access_type": "management_listing_collection",
        "resource": "listing_collection",
    }
    assert detail_log.actor == manager
    assert detail_log.entity_type == "Listing"
    assert detail_log.entity_id == str(first_listing.pk)
    assert detail_log.after == {"access_type": "management_listing_detail", "listing_id": first_listing.listing_id}
    assert second_listing.listing_id not in rendered_metadata(collection_log)
    assert_safe_listing_metadata(collection_log)
    assert_safe_listing_metadata(detail_log)


def test_lister_and_failed_reads_do_not_log_sensitive_access():
    lister = create_user("listing-own-read-lister@example.test")
    other = create_user("listing-own-read-other@example.test")
    revoked_manager = create_user("listing-own-read-revoked@example.test")
    grant_role(lister, ROLE_OWNER)
    grant_role(other, ROLE_OWNER)
    grant_role(revoked_manager, ROLE_MANAGEMENT, is_active=False)
    listing = create_listing_direct(lister)
    before = AuditLog.objects.filter(action="sensitive_data.accessed").count()

    assert client_for(lister).get("/api/v1/listings/").status_code == 200
    assert client_for(lister).get(f"/api/v1/listings/{listing.listing_id}/").status_code == 200
    assert client_for(other).get(f"/api/v1/listings/{listing.listing_id}/").status_code == 403
    assert client_for(revoked_manager).get(f"/api/v1/listings/{listing.listing_id}/").status_code == 403
    assert client_for(lister).get("/api/v1/listings/LST-MISSING/").status_code == 404

    assert AuditLog.objects.filter(action="sensitive_data.accessed").count() == before


def test_listing_hard_delete_admin_and_api_are_disabled():
    lister = create_user("listing-delete-policy@example.test")
    grant_role(lister, ROLE_OWNER)
    listing = create_listing_direct(lister)

    with pytest.raises(RuntimeError):
        listing.delete()
    with pytest.raises(RuntimeError):
        Listing.objects.filter(pk=listing.pk).delete()

    model_admin = ListingAdmin(Listing, admin.site)
    request = APIRequestFactory().get("/admin/")
    request.user = lister
    assert not model_admin.has_delete_permission(request)

    client = client_for(lister)
    assert client.delete(f"/api/v1/listings/{listing.listing_id}/").status_code == 405
    assert client.put(f"/api/v1/listings/{listing.listing_id}/", {}, format="json").status_code == 405
