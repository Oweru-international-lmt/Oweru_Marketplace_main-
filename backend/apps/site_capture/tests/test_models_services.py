import re
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point, Polygon
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.models import AuditLog
from apps.localities.models import District, Locality, Region, Ward
from apps.properties.models import PropertyRecord
from apps.properties.services import create_property_record
from apps.roles.catalog import ROLE_OWNER
from apps.roles.models import Role, UserRole
from apps.roles.services import bootstrap_canonical_roles
from apps.site_capture.audit_events import SITE_CAPTURE_CREATED, SITE_CAPTURE_SUBMITTED, SITE_CAPTURE_UPDATED
from apps.site_capture.models import SiteCapture
from apps.site_capture.services import create_site_capture, generate_capture_id, submit_site_capture, update_site_capture
from apps.verification.services import get_effective_verification_level


pytestmark = pytest.mark.django_db


def create_user(email):
    return get_user_model().objects.create_user(
        email=email,
        phone=f"+255{abs(hash(email)) % 1000000000:09d}",
        full_name="Site Capture User",
        password="StrongPass123!",
    )


def grant_owner(user):
    bootstrap_canonical_roles()
    role = Role.objects.get(code=ROLE_OWNER)
    UserRole.objects.create(user=user, role=role)


def create_hierarchy(prefix="Capture"):
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


def create_property(owner, prefix="Capture"):
    region, district, ward, locality = create_hierarchy(prefix)
    return create_property_record(
        actor=owner,
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
    )


def make_owner_and_property(prefix="Capture"):
    owner = create_user(f"{prefix.lower()}@example.test")
    grant_owner(owner)
    return owner, create_property(owner, prefix)


def observed_point():
    return Point(39.2100, -6.7900, srid=4326)


def observed_boundary():
    return Polygon(
        ((39.209, -6.791), (39.211, -6.791), (39.211, -6.789), (39.209, -6.791)),
        srid=4326,
    )


def create_capture(owner, property_record, **overrides):
    values = {"observed_point": observed_point(), "observed_boundary": None}
    values.update(overrides)
    return create_site_capture(property_record=property_record, actor=owner, **values)


def test_model_has_required_fields_default_draft_and_optional_boundary():
    owner, property_record = make_owner_and_property("Model")
    capture = SiteCapture.objects.create(
        capture_id="CAP-0123456789ABCDEF",
        property=property_record,
        captured_by=owner,
        captured_at=timezone.now(),
        observed_point=observed_point(),
    )

    assert capture.status == SiteCapture.Status.DRAFT
    assert capture.observed_boundary is None
    assert capture.observed_point.srid == 4326


def test_model_enforces_unique_capture_id_and_required_observed_point():
    owner, property_record = make_owner_and_property("Constraints")
    SiteCapture.objects.create(
        capture_id="CAP-1111111111111111",
        property=property_record,
        captured_by=owner,
        captured_at=timezone.now(),
        observed_point=observed_point(),
    )

    with transaction.atomic():
        with pytest.raises(IntegrityError):
            SiteCapture.objects.create(
                capture_id="CAP-1111111111111111",
                property=property_record,
                captured_by=owner,
                captured_at=timezone.now(),
                observed_point=observed_point(),
            )

    with pytest.raises(DjangoValidationError) as error:
        SiteCapture(
            capture_id="CAP-2222222222222222",
            property=property_record,
            captured_by=owner,
            captured_at=timezone.now(),
        ).full_clean()
    assert "observed_point" in error.value.message_dict


def test_capture_id_generation_retries_collisions_with_a_new_server_generated_token(monkeypatch):
    owner, property_record = make_owner_and_property("CaptureIdCollision")
    existing_token = "A" * 16
    replacement_token = "B" * 16
    SiteCapture.objects.create(
        capture_id=f"CAP-{existing_token}",
        property=property_record,
        captured_by=owner,
        captured_at=timezone.now(),
        observed_point=observed_point(),
    )
    tokens = iter([existing_token, replacement_token])
    monkeypatch.setattr("apps.site_capture.services._capture_id_token", lambda: next(tokens))

    capture_id = generate_capture_id()

    assert capture_id == f"CAP-{replacement_token}"


def test_model_requires_property_and_limits_status_choices_with_server_fields_non_null():
    with pytest.raises(DjangoValidationError) as error:
        SiteCapture(
            capture_id="CAP-3333333333333333",
            observed_point=observed_point(),
            status="UNSUPPORTED",
        ).full_clean()

    assert {"property", "status"}.issubset(error.value.message_dict)
    for field_name in ("captured_by", "captured_at", "observed_point"):
        assert SiteCapture._meta.get_field(field_name).null is False


def test_create_service_generates_private_draft_without_changing_property_or_verification():
    owner, property_record = make_owner_and_property("Create")
    original_pin = property_record.pin.clone()
    initial_level = get_effective_verification_level(user=owner, property_record=property_record)
    before = timezone.now()

    capture = create_capture(owner, property_record, observed_boundary=observed_boundary())

    property_record.refresh_from_db()
    assert re.fullmatch(r"CAP-[0-9A-F]{16}", capture.capture_id)
    assert capture.status == SiteCapture.Status.DRAFT
    assert capture.captured_by_id == owner.id
    assert before <= capture.captured_at <= timezone.now()
    assert capture.observed_boundary.srid == 4326
    assert property_record.pin.equals_exact(original_pin, tolerance=0)
    assert get_effective_verification_level(user=owner, property_record=property_record) == initial_level


def test_create_service_requires_existing_property_update_authorization():
    owner, property_record = make_owner_and_property("CreateDenied")
    unrelated = create_user("unrelated@example.test")

    with pytest.raises(PermissionDenied):
        create_capture(unrelated, property_record)

    assert SiteCapture.objects.count() == 0
    assert not AuditLog.objects.filter(action=SITE_CAPTURE_CREATED).exists()


def test_update_service_changes_only_draft_observations_and_audits_field_names():
    owner, property_record = make_owner_and_property("Update")
    capture = create_capture(owner, property_record)
    updated_point = Point(39.2200, -6.7800, srid=4326)

    updated = update_site_capture(
        site_capture=capture,
        actor=owner,
        observed_point=updated_point,
        observed_boundary=observed_boundary(),
    )

    assert updated.observed_point.equals_exact(updated_point, tolerance=0)
    assert updated.observed_boundary.srid == 4326
    audit = AuditLog.objects.get(action=SITE_CAPTURE_UPDATED, entity_id=str(capture.pk))
    assert audit.after == {
        "capture_id": capture.capture_id,
        "property_id": str(property_record.pk),
        "changed_fields": ["observed_boundary", "observed_point"],
    }
    assert "39.2200" not in str(audit.after)


def test_update_same_value_is_safe_noop_without_misleading_audit():
    owner, property_record = make_owner_and_property("Noop")
    capture = create_capture(owner, property_record)

    updated = update_site_capture(site_capture=capture, actor=owner, observed_point=capture.observed_point)

    assert updated.pk == capture.pk
    assert not AuditLog.objects.filter(action=SITE_CAPTURE_UPDATED).exists()


@pytest.mark.parametrize("field,value", [
    ("capture_id", "CAP-FFFFFFFFFFFFFFFF"),
    ("property", None),
    ("captured_by", None),
    ("captured_at", timezone.now()),
    ("status", SiteCapture.Status.SUBMITTED),
    ("created_at", timezone.now()),
    ("updated_at", timezone.now()),
    ("unknown", "value"),
])
def test_update_rejects_protected_and_unknown_fields(field, value):
    owner, property_record = make_owner_and_property(f"Protected{field}")
    capture = create_capture(owner, property_record)

    with pytest.raises(ValidationError) as error:
        update_site_capture(site_capture=capture, actor=owner, **{field: value})

    assert field in error.value.detail
    capture.refresh_from_db()
    assert capture.status == SiteCapture.Status.DRAFT
    assert capture.property_id == property_record.pk


def test_update_requires_property_authorization():
    owner, property_record = make_owner_and_property("UpdateDenied")
    capture = create_capture(owner, property_record)
    unrelated = create_user("update-unrelated@example.test")

    with pytest.raises(PermissionDenied):
        update_site_capture(site_capture=capture, actor=unrelated, observed_point=Point(39.22, -6.78, srid=4326))

    assert not AuditLog.objects.filter(action=SITE_CAPTURE_UPDATED).exists()


def test_submit_transitions_draft_once_and_preserves_observations():
    owner, property_record = make_owner_and_property("Submit")
    capture = create_capture(owner, property_record, observed_boundary=observed_boundary())
    original_point = capture.observed_point.clone()
    original_boundary = capture.observed_boundary.clone()

    submitted = submit_site_capture(site_capture=capture, actor=owner)

    assert submitted.status == SiteCapture.Status.SUBMITTED
    assert submitted.observed_point.equals_exact(original_point, tolerance=0)
    assert submitted.observed_boundary.equals_exact(original_boundary, tolerance=0)
    audit = AuditLog.objects.get(action=SITE_CAPTURE_SUBMITTED, entity_id=str(capture.pk))
    assert audit.after == {
        "capture_id": capture.capture_id,
        "property_id": str(property_record.pk),
        "from_status": SiteCapture.Status.DRAFT,
        "to_status": SiteCapture.Status.SUBMITTED,
    }

    with pytest.raises(ValidationError):
        submit_site_capture(site_capture=capture, actor=owner)


def test_submitted_capture_is_immutable_through_services():
    owner, property_record = make_owner_and_property("Immutable")
    capture = submit_site_capture(site_capture=create_capture(owner, property_record), actor=owner)

    with pytest.raises(ValidationError):
        update_site_capture(site_capture=capture, actor=owner, observed_point=Point(39.24, -6.77, srid=4326))
    with pytest.raises(ValidationError):
        update_site_capture(site_capture=capture, actor=owner, property=property_record)


def test_capture_services_do_not_call_property_duplicate_detection(monkeypatch):
    owner, property_record = make_owner_and_property("NoDuplicate")
    calls = []

    def record_call(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr("apps.properties.services._run_duplicate_detection", record_call)
    capture = create_capture(owner, property_record)
    update_site_capture(site_capture=capture, actor=owner, observed_point=Point(39.23, -6.79, srid=4326))
    submit_site_capture(site_capture=capture, actor=owner)

    assert calls == []


def test_capture_audit_contains_only_safe_metadata():
    owner, property_record = make_owner_and_property("Audit")
    capture = create_capture(owner, property_record, observed_boundary=observed_boundary())
    update_site_capture(site_capture=capture, actor=owner, observed_point=Point(39.25, -6.75, srid=4326))
    submit_site_capture(site_capture=capture, actor=owner)

    events = list(AuditLog.objects.filter(entity_type="SiteCapture", entity_id=str(capture.pk)))
    assert {event.action for event in events} == {SITE_CAPTURE_CREATED, SITE_CAPTURE_UPDATED, SITE_CAPTURE_SUBMITTED}
    serialized = " ".join(str(event.before) + str(event.after) for event in events)
    for forbidden in ("POINT", "POLYGON", "39.25", "-6.75"):
        assert forbidden not in serialized


def test_required_audit_failure_rolls_back_capture_creation(monkeypatch):
    owner, property_record = make_owner_and_property("AuditRollback")

    def fail_audit(**kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr("apps.site_capture.services.create_audit_log", fail_audit)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        create_capture(owner, property_record)

    assert SiteCapture.objects.count() == 0


def test_capture_service_requires_active_persisted_actor():
    owner, property_record = make_owner_and_property("Inactive")
    owner.is_active = False
    owner.save(update_fields=["is_active"])

    with pytest.raises(PermissionDenied):
        create_capture(owner, property_record)
