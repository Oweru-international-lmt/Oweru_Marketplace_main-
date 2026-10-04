from decimal import Decimal
import uuid

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point, Polygon
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient, APIRequestFactory

from apps.audit.models import AuditLog
from apps.localities.models import District, Locality, Region, Ward
from apps.properties.admin import PropertyRecordAdmin
from apps.properties.audit_events import PROPERTY_CREATED, PROPERTY_UPDATED
from apps.properties.models import PropertyRecord
from apps.properties.services import create_property_record, update_property_record
from apps.roles.catalog import ROLE_AGENT, ROLE_BUYER, ROLE_MANAGEMENT, ROLE_OWNER
from apps.roles.models import Role, UserRole
from apps.roles.services import bootstrap_canonical_roles


pytestmark = pytest.mark.django_db

SENSITIVE_MARKERS = (
    "password",
    "password_hash",
    "access",
    "refresh",
    "jwt",
    "token",
    "secret",
    "verification_token",
    "reset_token",
    "national_id",
    "national_id_number",
    "national_id_photo_ref",
    "live_selfie_ref",
    "email",
    "phone",
    "coordinates",
    "latitude",
    "longitude",
    "Point",
    "Polygon",
    "POLYGON",
    "POINT",
)


def create_user(email=None, *, is_active=True):
    return get_user_model().objects.create_user(
        email=email or f"property-audit-{uuid.uuid4().hex[:10]}@example.test",
        phone=f"+255{uuid.uuid4().int % 1000000000:09d}",
        full_name="Property Audit User",
        password="StrongPass123!",
        is_active=is_active,
    )


def grant_role(user, role_code, *, is_active=True, role_active=True):
    bootstrap_canonical_roles()
    role = Role.objects.get(code=role_code)
    role.is_active = role_active
    role.save(update_fields=["is_active"])
    return UserRole.objects.create(user=user, role=role, assigned_by=user, is_active=is_active)


def user_with_role(role_code, email=None, **kwargs):
    user = create_user(email=email, is_active=kwargs.pop("is_active", True))
    grant_role(user, role_code, **kwargs)
    return user


def authenticated_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def create_hierarchy(prefix="Audit", *, approved=True):
    region = Region.objects.create(name=f"{prefix} Region")
    district = District.objects.create(region=region, name=f"{prefix} District")
    ward = Ward.objects.create(district=district, name=f"{prefix} Ward")
    locality = Locality.objects.create(
        ward=ward,
        name=f"{prefix} Street",
        kind=Locality.Kind.STREET,
        approved=approved,
    )
    return region, district, ward, locality


def attrs(prefix="Audit", **overrides):
    region, district, ward, locality = create_hierarchy(prefix)
    data = {
        "category": PropertyRecord.Category.LAND,
        "pin": Point(39.2083, -6.7924, srid=4326),
        "boundary": None,
        "region": region,
        "district": district,
        "ward": ward,
        "locality": locality,
        "stated_size": Decimal("1200.50"),
        "size_unit": "sqm",
        "title_type": PropertyRecord.TitleType.UNKNOWN,
    }
    data.update(overrides)
    return data


def typed_attrs(prefix="TypedAudit", *, name="Typed Audit Street", kind=Locality.Kind.STREET, **overrides):
    data = attrs(prefix)
    data.pop("locality")
    data["locality_name"] = name
    data["locality_kind"] = kind
    data.update(overrides)
    return data


def latest(action):
    return AuditLog.objects.filter(action=action).latest("created_at")


def rendered_metadata(log):
    return (repr(log.before) + repr(log.after)).lower()


def assert_safe_property_metadata(log):
    rendered = rendered_metadata(log)
    for marker in SENSITIVE_MARKERS:
        assert marker.lower() not in rendered


def assert_sensitive_access_metadata_has_no_private_property_data(log):
    rendered = rendered_metadata(log)
    for marker in ("coordinates", "latitude", "longitude", "point", "polygon", "email", "phone", "password", "token"):
        assert marker not in rendered


def test_successful_create_creates_one_safe_property_audit_event():
    owner = user_with_role(ROLE_OWNER)
    boundary = Polygon(((39.20, -6.79), (39.21, -6.79), (39.21, -6.80), (39.20, -6.80), (39.20, -6.79)), srid=4326)

    record = create_property_record(actor=owner, **attrs("CreateAudit", boundary=boundary))

    logs = AuditLog.objects.filter(action=PROPERTY_CREATED)
    assert logs.count() == 1
    log = logs.get()
    assert log.actor == owner
    assert log.entity_type == "PropertyRecord"
    assert log.entity_id == str(record.pk)
    assert log.after == {
        "property_id": record.property_id,
        "category": PropertyRecord.Category.LAND,
        "locality_id": str(record.locality_id),
        "locality_approved": True,
        "size_unit": "sqm",
    }
    assert_safe_property_metadata(log)


def test_failed_or_unauthorized_create_does_not_audit_success():
    buyer = user_with_role(ROLE_BUYER)
    with pytest.raises(PermissionDenied):
        create_property_record(actor=buyer, **typed_attrs("DeniedCreateAudit", name="Denied Audit Street"))

    owner = user_with_role(ROLE_OWNER)
    bad = attrs("InvalidCreateAudit", stated_size=Decimal("0"))
    with pytest.raises(ValidationError):
        create_property_record(actor=owner, **bad)

    assert not AuditLog.objects.filter(action=PROPERTY_CREATED).exists()
    assert not Locality.objects.filter(name__iexact="Denied Audit Street").exists()


def test_create_audit_failure_rolls_back_property_and_pending_locality(monkeypatch):
    owner = user_with_role(ROLE_OWNER)

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr("apps.properties.services.create_audit_log", fail_audit)
    with pytest.raises(RuntimeError):
        create_property_record(actor=owner, **typed_attrs("CreateAuditRollback", name="Rollback Audit Street"))

    assert not PropertyRecord.objects.exists()
    assert not Locality.objects.filter(name__iexact="Rollback Audit Street").exists()


def test_property_id_collision_retry_creates_exactly_one_audit_event(monkeypatch):
    from apps.properties import services

    owner = user_with_role(ROLE_OWNER)
    existing = create_property_record(actor=owner, **attrs("CollisionExisting"))
    tokens = iter([existing.property_id.removeprefix("OWR-"), "ABCDEF1234567890"])
    monkeypatch.setattr(services, "_property_id_token", lambda: next(tokens))

    record = create_property_record(actor=owner, **attrs("CollisionRetry"))

    assert record.property_id == "OWR-ABCDEF1234567890"
    assert AuditLog.objects.filter(action=PROPERTY_CREATED, entity_id=str(record.pk)).count() == 1


def test_successful_creator_and_management_updates_create_safe_changed_field_audits():
    creator = user_with_role(ROLE_OWNER)
    manager = user_with_role(ROLE_MANAGEMENT)
    record = create_property_record(actor=creator, **attrs("UpdateAudit"))
    boundary = Polygon(((39.22, -6.81), (39.23, -6.81), (39.23, -6.82), (39.22, -6.82), (39.22, -6.81)), srid=4326)

    update_property_record(
        actor=creator,
        property_record=record,
        category=PropertyRecord.Category.HOUSE,
        pin=Point(39.3, -6.9, srid=4326),
        boundary=boundary,
    )
    creator_log = latest(PROPERTY_UPDATED)
    assert creator_log.actor == creator
    assert creator_log.entity_type == "PropertyRecord"
    assert creator_log.entity_id == str(record.pk)
    assert creator_log.after["changed_fields"] == ["boundary", "category", "pin"]
    assert_safe_property_metadata(creator_log)

    update_property_record(actor=manager, property_record=record, title_type=PropertyRecord.TitleType.CCRO)
    manager_log = latest(PROPERTY_UPDATED)
    assert manager_log.actor == manager
    assert manager_log.after["changed_fields"] == ["title_type"]
    assert_safe_property_metadata(manager_log)


def test_noop_update_does_not_create_property_updated_event():
    creator = user_with_role(ROLE_OWNER)
    record = create_property_record(actor=creator, **attrs("NoopAudit"))
    before = AuditLog.objects.filter(action=PROPERTY_UPDATED).count()

    update_property_record(actor=creator, property_record=record, stated_size=record.stated_size)

    assert AuditLog.objects.filter(action=PROPERTY_UPDATED).count() == before


def test_failed_or_unauthorized_update_does_not_audit_success():
    creator = user_with_role(ROLE_OWNER)
    unrelated = user_with_role(ROLE_AGENT)
    record = create_property_record(actor=creator, **attrs("DeniedUpdateAudit"))
    before = AuditLog.objects.filter(action=PROPERTY_UPDATED).count()

    with pytest.raises(PermissionDenied):
        update_property_record(actor=unrelated, property_record=record, category=PropertyRecord.Category.HOUSE)

    _, _, _, other_locality = create_hierarchy("InvalidUpdateAudit")
    with pytest.raises(ValidationError):
        update_property_record(actor=creator, property_record=record, locality=other_locality)

    assert AuditLog.objects.filter(action=PROPERTY_UPDATED).count() == before


def test_update_audit_failure_rolls_back_property_and_pending_locality(monkeypatch):
    creator = user_with_role(ROLE_OWNER)
    record = create_property_record(actor=creator, **attrs("UpdateRollback"))
    original_category = record.category
    original_locality_id = record.locality_id
    before = AuditLog.objects.filter(action=PROPERTY_UPDATED).count()

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr("apps.properties.services.create_audit_log", fail_audit)
    with pytest.raises(RuntimeError):
        update_property_record(
            actor=creator,
            property_record=record,
            category=PropertyRecord.Category.COMMERCIAL,
            locality_name="Update Rollback Street",
            locality_kind=Locality.Kind.STREET,
        )

    record.refresh_from_db()
    assert record.category == original_category
    assert record.locality_id == original_locality_id
    assert not Locality.objects.filter(name__iexact="Update Rollback Street").exists()
    assert AuditLog.objects.filter(action=PROPERTY_UPDATED).count() == before


def test_private_management_cross_user_detail_logs_sensitive_access_without_geometry():
    creator = user_with_role(ROLE_OWNER)
    manager = user_with_role(ROLE_MANAGEMENT)
    record = create_property_record(actor=creator, **attrs("SensitiveRead"))

    response = authenticated_client(manager).get(f"/api/v1/properties/{record.property_id}/")

    assert response.status_code == 200
    log = AuditLog.objects.get(action="sensitive_data.accessed")
    assert log.actor == manager
    assert log.entity_type == "PropertyRecord"
    assert log.entity_id == str(record.pk)
    assert log.after == {"access_type": "management_property_detail", "property_id": record.property_id}
    assert_sensitive_access_metadata_has_no_private_property_data(log)


def test_creator_list_unauthorized_and_missing_reads_do_not_log_sensitive_access():
    creator = user_with_role(ROLE_OWNER)
    unrelated = user_with_role(ROLE_AGENT)
    record = create_property_record(actor=creator, **attrs("NoSensitiveRead"))
    before = AuditLog.objects.filter(action="sensitive_data.accessed").count()

    assert authenticated_client(creator).get(f"/api/v1/properties/{record.property_id}/").status_code == 200
    assert authenticated_client(creator).get("/api/v1/properties/").status_code == 200
    assert authenticated_client(unrelated).get(f"/api/v1/properties/{record.property_id}/").status_code == 403
    assert authenticated_client(creator).get("/api/v1/properties/OWR-MISSING/").status_code == 404

    assert AuditLog.objects.filter(action="sensitive_data.accessed").count() == before


def test_property_permanence_model_queryset_admin_and_api():
    creator = user_with_role(ROLE_OWNER)
    record = create_property_record(actor=creator, **attrs("Permanent"))

    with pytest.raises(RuntimeError):
        record.delete()
    with pytest.raises(RuntimeError):
        PropertyRecord.objects.filter(pk=record.pk).delete()

    model_admin = PropertyRecordAdmin(PropertyRecord, admin.site)
    request = APIRequestFactory().get("/admin/")
    request.user = creator
    assert not model_admin.has_delete_permission(request)

    client = authenticated_client(creator)
    assert client.delete(f"/api/v1/properties/{record.property_id}/").status_code == 405
    assert client.put(f"/api/v1/properties/{record.property_id}/", {}, format="json").status_code == 405
