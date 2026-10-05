from decimal import Decimal
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.db import connection
from django.db.models import Q
from rest_framework.exceptions import ValidationError

from apps.localities.models import District, Locality, Region, Ward
from apps.properties.duplicate_services import (
    detect_property_duplicates,
    dismiss_possible_duplicate,
    record_possible_duplicate,
    size_difference_percent,
)
from apps.properties.models import PossibleDuplicate, PropertyRecord
from apps.properties.services import create_property_record, update_property_record
from apps.roles.catalog import ROLE_MANAGEMENT, ROLE_OWNER
from apps.roles.models import Role, UserRole
from apps.roles.services import bootstrap_canonical_roles


pytestmark = pytest.mark.django_db
requires_postgis = pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason="Requires PostgreSQL/PostGIS meter-distance spatial queries.",
)


def create_user(email=None):
    email = email or f"duplicate-detect-{uuid.uuid4().hex[:10]}@example.test"
    return get_user_model().objects.create_user(
        email=email,
        phone=f"+2557{uuid.uuid4().int % 100000000:08d}",
        full_name="Duplicate Detection User",
        password="StrongPass123!",
    )


def grant_role(user, role_code):
    bootstrap_canonical_roles()
    role = Role.objects.get(code=role_code)
    return UserRole.objects.create(user=user, role=role, assigned_by=user)


def lister(email=None):
    user = create_user(email)
    grant_role(user, ROLE_OWNER)
    return user


def manager(email=None):
    user = create_user(email)
    grant_role(user, ROLE_MANAGEMENT)
    return user


def hierarchy(prefix=None):
    prefix = prefix or f"DuplicateDetect{uuid.uuid4().hex[:8]}"
    region = Region.objects.create(name=f"{prefix} Region")
    district = District.objects.create(region=region, name=f"{prefix} District")
    ward = Ward.objects.create(district=district, name=f"{prefix} Ward")
    locality = Locality.objects.create(ward=ward, name=f"{prefix} Street", kind=Locality.Kind.STREET, approved=True)
    return region, district, ward, locality


def property_attrs(prefix=None, **overrides):
    region, district, ward, locality = hierarchy(prefix)
    attrs = {
        "category": PropertyRecord.Category.LAND,
        "pin": Point(39.2083, -6.7924, srid=4326),
        "boundary": None,
        "region": region,
        "district": district,
        "ward": ward,
        "locality": locality,
        "stated_size": Decimal("1000.00"),
        "size_unit": "sqm",
        "title_type": PropertyRecord.TitleType.UNKNOWN,
    }
    attrs.update(overrides)
    return attrs


def direct_property(*, owner=None, prefix=None, point=None, size=Decimal("1000.00")):
    return PropertyRecord.objects.create(
        property_id=f"OWR-{uuid.uuid4().hex[:16].upper()}",
        created_by=owner or create_user(),
        **property_attrs(prefix=prefix, pin=point or Point(39.2083, -6.7924, srid=4326), stated_size=size),
    )


def projected_point(origin, meters, *, azimuth_degrees=90):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT ST_X(projected.geom), ST_Y(projected.geom)
            FROM (
                SELECT ST_Project(
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                    %s,
                    radians(%s)
                )::geometry AS geom
            ) AS projected
            """,
            [origin.x, origin.y, float(meters), float(azimuth_degrees)],
        )
        longitude, latitude = cursor.fetchone()
    return Point(longitude, latitude, srid=4326)


def duplicate_between(first, second):
    return PossibleDuplicate.objects.get(
        Q(property_a=first, property_b=second) | Q(property_a=second, property_b=first)
    )


def test_detector_requires_persisted_property_record():
    with pytest.raises(ValidationError):
        detect_property_duplicates(property_record=PropertyRecord())


def test_size_difference_percent_is_symmetric_and_boundary_aware():
    assert size_difference_percent(Decimal("1000.00"), Decimal("900.00")) == Decimal("10.00")
    assert size_difference_percent(Decimal("900.00"), Decimal("1000.00")) == Decimal("10.00")
    assert size_difference_percent(Decimal("1000.00"), Decimal("1111.12")) == Decimal("10.00")
    assert size_difference_percent(Decimal("1000.00"), Decimal("1250.00")) == Decimal("20.00")


@requires_postgis
def test_postgis_detector_uses_meter_distance_threshold(settings):
    settings.PROPERTY_DUPLICATE_DISTANCE_METERS = 50
    origin = Point(39.2083, -6.7924, srid=4326)
    subject = direct_property(prefix="DistanceSubject", point=origin)
    exact_boundary = direct_property(prefix="DistanceExact", point=projected_point(origin, Decimal("50.00")))
    direct_property(prefix="DistanceOutside", point=projected_point(origin, Decimal("50.01")))

    candidates = detect_property_duplicates(property_record=subject)

    assert candidates == [duplicate_between(subject, exact_boundary)]
    assert candidates[0].distance_meters == Decimal("50.00")


@requires_postgis
def test_postgis_detector_applies_size_threshold_and_never_photo_signal(settings):
    settings.PROPERTY_DUPLICATE_DISTANCE_METERS = 50
    settings.PROPERTY_DUPLICATE_SIZE_DIFFERENCE_PERCENT = 10
    origin = Point(39.2083, -6.7924, srid=4326)
    subject = direct_property(prefix="SizeSubject", point=origin, size=Decimal("1000.00"))
    exact_size = direct_property(prefix="SizeExact", point=projected_point(origin, Decimal("20.00")), size=Decimal("900.00"))
    different_size = direct_property(
        prefix="SizeDifferent",
        point=projected_point(origin, Decimal("30.00")),
        size=Decimal("1250.00"),
    )

    detect_property_duplicates(property_record=subject)

    exact_candidate = duplicate_between(subject, exact_size)
    different_candidate = duplicate_between(subject, different_size)
    assert exact_candidate.signals == [
        PossibleDuplicate.SIGNAL_PIN_PROXIMITY,
        PossibleDuplicate.SIGNAL_SIZE_SIMILARITY,
    ]
    assert different_candidate.signals == [PossibleDuplicate.SIGNAL_PIN_PROXIMITY]
    assert not PossibleDuplicate.objects.filter(signals__contains=[PossibleDuplicate.SIGNAL_PHOTO_SIMILARITY]).exists()


@requires_postgis
def test_detector_is_idempotent_and_preserves_review_state(settings):
    settings.PROPERTY_DUPLICATE_DISTANCE_METERS = 50
    origin = Point(39.2083, -6.7924, srid=4326)
    subject = direct_property(prefix="IdempotentSubject", point=origin)
    nearby = direct_property(prefix="IdempotentNearby", point=projected_point(origin, Decimal("12.00")))

    first = detect_property_duplicates(property_record=subject)[0]
    dismiss_possible_duplicate(actor=manager(), possible_duplicate=first, review_note="separate records")
    second = detect_property_duplicates(property_record=nearby)[0]

    assert first.pk == second.pk
    assert PossibleDuplicate.objects.count() == 1
    second.refresh_from_db()
    assert second.status == PossibleDuplicate.Status.NOT_DUPLICATE
    assert second.review_note == "separate records"


def test_create_property_record_runs_advisory_duplicate_detection(monkeypatch):
    calls = []

    def fake_detector(*, property_record, request=None):
        calls.append(property_record.pk)
        return []

    monkeypatch.setattr("apps.properties.services.detect_property_duplicates", fake_detector)
    actor = lister()
    record = create_property_record(actor=actor, **property_attrs(prefix="CreateHook"))

    assert calls == [record.pk]


def test_update_runs_detection_only_for_pin_or_size_changes(monkeypatch):
    calls = []

    def fake_detector(*, property_record, request=None):
        calls.append(property_record.pk)
        return []

    monkeypatch.setattr("apps.properties.services.detect_property_duplicates", fake_detector)
    actor = lister()
    record = create_property_record(actor=actor, **property_attrs(prefix="UpdateHook"))
    calls.clear()

    update_property_record(actor=actor, property_record=record, category=PropertyRecord.Category.HOUSE)
    update_property_record(actor=actor, property_record=record, stated_size=Decimal("1100.00"))
    update_property_record(actor=actor, property_record=record, pin=Point(39.2090, -6.7924, srid=4326))

    assert calls == [record.pk, record.pk]


def test_advisory_detection_validation_error_does_not_block_create_or_update(monkeypatch):
    def failing_detector(*, property_record, request=None):
        raise ValidationError({"duplicate_detection": "temporary spatial validation issue"})

    monkeypatch.setattr("apps.properties.services.detect_property_duplicates", failing_detector)
    actor = lister()

    record = create_property_record(actor=actor, **property_attrs(prefix="RecoverCreate"))
    updated = update_property_record(actor=actor, property_record=record, stated_size=Decimal("1200.00"))

    assert PropertyRecord.objects.filter(pk=record.pk).exists()
    assert updated.stated_size == Decimal("1200.00")


def test_stale_candidates_are_preserved_when_property_moves_away(monkeypatch):
    monkeypatch.setattr("apps.properties.services.detect_property_duplicates", lambda *, property_record, request=None: [])
    actor = lister()
    subject = direct_property(owner=actor, prefix="StaleSubject")
    nearby = direct_property(owner=actor, prefix="StaleNearby")
    candidate = record_possible_duplicate(
        property_a=subject,
        property_b=nearby,
        signals=[PossibleDuplicate.SIGNAL_PIN_PROXIMITY],
    )

    update_property_record(actor=actor, property_record=subject, pin=Point(40.0, -7.0, srid=4326))

    assert PossibleDuplicate.objects.filter(pk=candidate.pk).exists()
    assert PropertyRecord.objects.filter(pk__in=[subject.pk, nearby.pk]).count() == 2
