from decimal import Decimal
from unittest.mock import patch
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point, Polygon
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.models import AuditLog
from apps.properties.audit_events import PROPERTY_UPDATED
from apps.properties.models import PropertyRecord
from apps.properties.services import update_property_record
from apps.roles.catalog import ROLE_AGENT, ROLE_LOCAL_OFFICIAL, ROLE_MANAGEMENT, ROLE_OWNER, ROLE_PROFESSIONAL, ROLE_VERIFIER
from apps.roles.models import Role, UserRole
from apps.roles.services import bootstrap_canonical_roles
from apps.localities.models import District, Locality, Region, Ward
from apps.site_capture.audit_events import SITE_CAPTURE_PROMOTED
from apps.site_capture.models import SiteCapture
from apps.site_capture.services import create_site_capture, promote_site_capture, submit_site_capture
from apps.verification.services import get_effective_verification_level


pytestmark = pytest.mark.django_db


def create_user(email=None):
    email = email or f"promotion-{uuid.uuid4().hex[:10]}@example.test"
    return get_user_model().objects.create_user(
        email=email,
        phone=f"+2557{abs(hash(email)) % 100000000:08d}",
        full_name="Site Capture Promotion User",
        password="StrongPass123!",
    )


def grant_role(user, role_code):
    bootstrap_canonical_roles()
    return UserRole.objects.create(user=user, role=Role.objects.get(code=role_code))


def property_record(owner, prefix=None):
    prefix = prefix or f"Promotion{uuid.uuid4().hex[:8]}"
    region = Region.objects.create(name=f"{prefix} Region")
    district = District.objects.create(region=region, name=f"{prefix} District")
    ward = Ward.objects.create(district=district, name=f"{prefix} Ward")
    locality = Locality.objects.create(ward=ward, name=f"{prefix} Street", kind=Locality.Kind.STREET, approved=True)
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
        created_by=owner,
    )


def observed_boundary():
    return Polygon(
        ((39.240, -6.800), (39.260, -6.800), (39.260, -6.780), (39.240, -6.800)),
        srid=4326,
    )


def owner_property_capture(prefix="Promotion", *, boundary=None, submitted=True):
    owner = create_user(f"{prefix.lower()}@example.test")
    grant_role(owner, ROLE_OWNER)
    property_record_instance = property_record(owner, prefix)
    site_capture = create_site_capture(
        property_record=property_record_instance,
        actor=owner,
        observed_point=Point(39.25, -6.79, srid=4326),
        observed_boundary=boundary if boundary is not None else (observed_boundary() if submitted else None),
    )
    if submitted:
        site_capture = submit_site_capture(site_capture=site_capture, actor=owner)
    return owner, property_record_instance, site_capture


def test_submitted_capture_explicit_point_promotion_uses_property_service_and_preserves_history(monkeypatch):
    owner, property_record_instance, site_capture = owner_property_capture("Point")
    original_capture_point = site_capture.observed_point.clone()
    original_capture_time = site_capture.captured_at
    calls = []
    from apps.site_capture import services as capture_services

    original_update = capture_services.update_property_record

    def update_spy(**kwargs):
        calls.append(kwargs)
        return original_update(**kwargs)

    monkeypatch.setattr(capture_services, "update_property_record", update_spy)
    promoted = promote_site_capture(site_capture=site_capture, actor=owner, promote_point=True, promote_boundary=False)

    assert calls and calls[0]["pin"].equals_exact(original_capture_point, tolerance=0)
    assert promoted.pin.equals_exact(original_capture_point, tolerance=0)
    assert promoted.pin.srid == 4326
    site_capture.refresh_from_db()
    assert site_capture.status == SiteCapture.Status.SUBMITTED
    assert site_capture.observed_point.equals_exact(original_capture_point, tolerance=0)
    assert site_capture.captured_at == original_capture_time
    assert AuditLog.objects.filter(action=PROPERTY_UPDATED, entity_id=str(property_record_instance.pk)).count() == 1
    assert AuditLog.objects.filter(action=SITE_CAPTURE_PROMOTED, entity_id=str(site_capture.pk)).count() == 1


def test_boundary_only_and_combined_promotion_are_explicit():
    owner, property_record_instance, site_capture = owner_property_capture("Boundary", boundary=observed_boundary())

    boundary_promoted = promote_site_capture(
        site_capture=site_capture,
        actor=owner,
        promote_point=False,
        promote_boundary=True,
    )
    assert boundary_promoted.pin.equals_exact(Point(39.2083, -6.7924, srid=4326), tolerance=0)
    assert boundary_promoted.boundary.equals_exact(site_capture.observed_boundary, tolerance=0)

    update_property_record(
        actor=owner,
        property_record=property_record_instance,
        pin=Point(39.30, -6.70, srid=4326),
        boundary=None,
    )
    combined = promote_site_capture(site_capture=site_capture, actor=owner, promote_point=True, promote_boundary=True)
    assert combined.pin.equals_exact(site_capture.observed_point, tolerance=0)
    assert combined.boundary.equals_exact(site_capture.observed_boundary, tolerance=0)


def test_promotion_selection_and_lifecycle_validation():
    owner, _, draft = owner_property_capture("Draft", submitted=False)
    with pytest.raises(ValidationError):
        promote_site_capture(site_capture=draft, actor=owner)

    submitted_owner, _, submitted = owner_property_capture("NoSelection")
    with pytest.raises(ValidationError):
        promote_site_capture(site_capture=submitted, actor=submitted_owner, promote_point=False, promote_boundary=False)
    with pytest.raises(ValidationError):
        promote_site_capture(site_capture=submitted, actor=submitted_owner, unexpected=True)
    with pytest.raises(ValidationError):
        promote_site_capture(site_capture=submitted, actor=submitted_owner, promote_point=True, promote_boundary="yes")
    # Boundary is now mandatory at submission, so a boundary-only promotion is valid.
    promoted = promote_site_capture(site_capture=submitted, actor=submitted_owner, promote_point=False, promote_boundary=True)
    assert promoted.boundary.equals_exact(submitted.observed_boundary, tolerance=0)


def test_promotion_authorization_uses_canonical_property_policy_only():
    owner, _, site_capture = owner_property_capture("Authorization")
    unrelated = create_user("promotion-unrelated@example.test")
    unrelated.role = ROLE_OWNER
    unrelated.roles = [ROLE_OWNER]
    verifier = create_user("promotion-verifier@example.test")
    grant_role(verifier, ROLE_VERIFIER)
    management = create_user("promotion-management@example.test")
    grant_role(management, ROLE_MANAGEMENT)

    with pytest.raises(PermissionDenied):
        promote_site_capture(site_capture=site_capture, actor=unrelated)
    with pytest.raises(PermissionDenied):
        promote_site_capture(site_capture=site_capture, actor=verifier)
    promoted = promote_site_capture(site_capture=site_capture, actor=management)
    assert promoted.pin.equals_exact(site_capture.observed_point, tolerance=0)


@pytest.mark.parametrize("role_code", [ROLE_OWNER, ROLE_AGENT, ROLE_VERIFIER, ROLE_LOCAL_OFFICIAL, ROLE_PROFESSIONAL])
def test_non_management_roles_and_staff_cannot_promote_another_users_capture(role_code):
    owner, _, site_capture = owner_property_capture(f"Role{role_code}")
    actor = create_user(f"promotion-{role_code.lower()}@example.test")
    grant_role(actor, role_code)
    actor.is_staff = True
    actor.is_superuser = True
    actor.save(update_fields=["is_staff", "is_superuser"])

    with pytest.raises(PermissionDenied):
        promote_site_capture(site_capture=site_capture, actor=actor)


def test_same_value_repeated_promotion_is_noop_without_false_audit_or_side_effects(monkeypatch):
    owner, property_record_instance, site_capture = owner_property_capture("Noop")
    update_property_record(actor=owner, property_record=property_record_instance, pin=site_capture.observed_point)
    duplicate_calls = []
    invalidation_calls = []
    monkeypatch.setattr("apps.properties.services._run_duplicate_detection", lambda *args, **kwargs: duplicate_calls.append(True))
    monkeypatch.setattr(
        "apps.properties.services.invalidate_property_verifications_for_material_change",
        lambda *args, **kwargs: invalidation_calls.append(kwargs),
    )

    promoted = promote_site_capture(site_capture=site_capture, actor=owner)

    assert promoted.pin.equals_exact(site_capture.observed_point, tolerance=0)
    assert duplicate_calls == []
    assert invalidation_calls == []
    assert not AuditLog.objects.filter(action=SITE_CAPTURE_PROMOTED).exists()


def test_changed_point_promotion_runs_canonical_duplicate_and_m14_invalidation_once(monkeypatch):
    owner, property_record_instance, site_capture = owner_property_capture("SideEffects", boundary=observed_boundary())
    duplicate_calls = []
    invalidation_calls = []
    monkeypatch.setattr("apps.properties.services._run_duplicate_detection", lambda *args, **kwargs: duplicate_calls.append(kwargs))
    monkeypatch.setattr(
        "apps.properties.services.invalidate_property_verifications_for_material_change",
        lambda *args, **kwargs: invalidation_calls.append(kwargs),
    )
    initial_level = get_effective_verification_level(user=owner, property_record=property_record_instance)

    promote_site_capture(site_capture=site_capture, actor=owner, promote_point=True, promote_boundary=True)

    assert len(duplicate_calls) == 1
    assert len(invalidation_calls) == 1
    assert invalidation_calls[0]["changed_fields"] == {"pin", "boundary"}
    assert get_effective_verification_level(user=owner, property_record=property_record_instance) == initial_level


def test_stale_submitted_capture_can_explicitly_restore_point():
    owner, property_record_instance, site_capture = owner_property_capture("Stale")
    update_property_record(actor=owner, property_record=property_record_instance, pin=Point(39.30, -6.70, srid=4326))

    promoted = promote_site_capture(site_capture=site_capture, actor=owner)

    assert promoted.pin.equals_exact(site_capture.observed_point, tolerance=0)


def test_property_failure_is_atomic_and_does_not_write_promotion_audit(monkeypatch):
    owner, property_record_instance, site_capture = owner_property_capture("Atomic")
    original_pin = property_record_instance.pin.clone()

    def fail_update(**kwargs):
        raise RuntimeError("property update failed")

    monkeypatch.setattr("apps.site_capture.services.update_property_record", fail_update)
    with pytest.raises(RuntimeError, match="property update failed"):
        promote_site_capture(site_capture=site_capture, actor=owner)

    property_record_instance.refresh_from_db()
    site_capture.refresh_from_db()
    assert property_record_instance.pin.equals_exact(original_pin, tolerance=0)
    assert site_capture.status == SiteCapture.Status.SUBMITTED
    assert not AuditLog.objects.filter(action=SITE_CAPTURE_PROMOTED).exists()


def test_promotion_audit_failure_rolls_back_canonical_property_update(monkeypatch):
    owner, property_record_instance, site_capture = owner_property_capture("AuditRollback")
    original_pin = property_record_instance.pin.clone()

    def fail_audit(**kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr("apps.site_capture.services.create_audit_log", fail_audit)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        promote_site_capture(site_capture=site_capture, actor=owner)

    property_record_instance.refresh_from_db()
    assert property_record_instance.pin.equals_exact(original_pin, tolerance=0)
    assert not AuditLog.objects.filter(action=SITE_CAPTURE_PROMOTED).exists()
    assert not AuditLog.objects.filter(action=PROPERTY_UPDATED).exists()


def test_promotion_audit_contains_only_safe_field_names():
    owner, _, site_capture = owner_property_capture("Audit", boundary=observed_boundary())
    promote_site_capture(site_capture=site_capture, actor=owner, promote_point=True, promote_boundary=True)

    audit = AuditLog.objects.get(action=SITE_CAPTURE_PROMOTED, entity_id=str(site_capture.pk))
    assert audit.after == {
        "capture_id": site_capture.capture_id,
        "property_id": str(site_capture.property_id),
        "promoted_fields": ["boundary", "pin"],
    }
    serialized = str(audit.after)
    for forbidden in ("POINT", "POLYGON", "39.25", "coordinates", "WKT", "WKB"):
        assert forbidden not in serialized
