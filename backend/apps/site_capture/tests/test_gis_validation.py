from decimal import Decimal
from math import inf, nan

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import LineString, MultiPolygon, Point, Polygon
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.localities.models import District, Locality, Region, Ward
from apps.properties.models import PropertyRecord
from apps.properties.services import create_property_record
from apps.roles.catalog import ROLE_OWNER
from apps.roles.models import Role, UserRole
from apps.roles.services import bootstrap_canonical_roles
from apps.site_capture.audit_events import SITE_CAPTURE_CREATED, SITE_CAPTURE_UPDATED
from apps.site_capture.models import SiteCapture
from apps.site_capture.services import create_site_capture, update_site_capture
from apps.verification.services import get_effective_verification_level


pytestmark = pytest.mark.django_db


def point_payload(longitude=39.21, latitude=-6.79):
    return {"type": "Point", "coordinates": [longitude, latitude]}


def polygon_payload():
    return {
        "type": "Polygon",
        "coordinates": [
            [[39.209, -6.791], [39.211, -6.791], [39.211, -6.789], [39.209, -6.791]],
        ],
    }


def create_user(email):
    return get_user_model().objects.create_user(
        email=email,
        phone=f"+255{abs(hash(email)) % 1000000000:09d}",
        full_name="Site Capture GIS User",
        password="StrongPass123!",
    )


def owner_and_property(prefix="GIS"):
    owner = create_user(f"{prefix.lower()}@example.test")
    bootstrap_canonical_roles()
    UserRole.objects.create(user=owner, role=Role.objects.get(code=ROLE_OWNER))
    region = Region.objects.create(name=f"{prefix} Region")
    district = District.objects.create(region=region, name=f"{prefix} District")
    ward = Ward.objects.create(district=district, name=f"{prefix} Ward")
    locality = Locality.objects.create(ward=ward, name=f"{prefix} Street", kind=Locality.Kind.STREET, approved=True)
    property_record = create_property_record(
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
    return owner, property_record


def create_capture(owner, property_record, **overrides):
    values = {"observed_point": point_payload(), "observed_boundary": None}
    values.update(overrides)
    return create_site_capture(property_record=property_record, actor=owner, **values)


@pytest.mark.parametrize("longitude,latitude", [(-180, -90), (-180, 90), (180, -90), (180, 90)])
def test_geojson_point_boundaries_are_accepted_and_normalized(longitude, latitude):
    owner, property_record = owner_and_property(f"PointBoundary{longitude}{latitude}")

    capture = create_capture(owner, property_record, observed_point=point_payload(longitude, latitude))

    assert capture.observed_point.srid == 4326
    assert (capture.observed_point.x, capture.observed_point.y) == (longitude, latitude)


@pytest.mark.parametrize(
    "value",
    [
        point_payload(-180.0001, 0),
        point_payload(180.0001, 0),
        point_payload(0, -90.0001),
        point_payload(0, 90.0001),
        {"type": "LineString", "coordinates": [[39.2, -6.7], [39.3, -6.8]]},
        polygon_payload(),
        {"type": "Point", "coordinates": [39.2]},
        {"type": "Point", "coordinates": [39.2, -6.7, 5]},
        {"type": "Point", "coordinates": ["east", -6.7]},
        {"type": "Point", "coordinates": [True, -6.7]},
        point_payload(nan, 0),
        point_payload(inf, 0),
        [],
    ],
)
def test_invalid_point_input_is_rejected_without_capture_or_audit(value):
    owner, property_record = owner_and_property(f"InvalidPoint{abs(hash(str(value)))}")

    with pytest.raises(ValidationError) as error:
        create_capture(owner, property_record, observed_point=value)

    assert "observed_point" in error.value.detail
    assert SiteCapture.objects.count() == 0
    assert not AuditLog.objects.filter(action=SITE_CAPTURE_CREATED).exists()


@pytest.mark.parametrize(
    "value",
    [
        {"type": "Polygon", "coordinates": [[[39.2, -6.7], [39.3, -6.7], [39.2, -6.8]]]},
        {"type": "Polygon", "coordinates": [[[39.2, -6.7], [39.3, -6.7], [39.2, -6.8], [39.21, -6.71]]]},
        {"type": "Polygon", "coordinates": ["not-a-ring"]},
        {"type": "Polygon", "coordinates": [[[181, -6.7], [39.3, -6.7], [39.2, -6.8], [181, -6.7]]]},
        {"type": "Polygon", "coordinates": [[[39.2, -6.7], ["east", -6.7], [39.2, -6.8], [39.2, -6.7]]]},
        {"type": "Polygon", "coordinates": [[[39.2, -6.7], [nan, -6.7], [39.2, -6.8], [39.2, -6.7]]]},
        {"type": "Polygon", "coordinates": [[[39.2, -6.7], [inf, -6.7], [39.2, -6.8], [39.2, -6.7]]]},
        {
            "type": "Polygon",
            "coordinates": [[[39.2, -6.8], [39.3, -6.7], [39.2, -6.7], [39.3, -6.8], [39.2, -6.8]]],
        },
        point_payload(),
        {"type": "MultiPolygon", "coordinates": []},
        {"type": "Polygon", "coordinates": []},
    ],
)
def test_invalid_polygon_input_is_rejected_without_capture_or_audit(value):
    owner, property_record = owner_and_property(f"InvalidPolygon{abs(hash(str(value)))}")

    with pytest.raises(ValidationError) as error:
        create_capture(owner, property_record, observed_boundary=value)

    assert "observed_boundary" in error.value.detail
    assert SiteCapture.objects.count() == 0
    assert not AuditLog.objects.filter(action=SITE_CAPTURE_CREATED).exists()


def test_geojson_polygon_is_normalized_and_null_explicitly_clears_it():
    owner, property_record = owner_and_property("BoundaryClear")
    capture = create_capture(owner, property_record, observed_boundary=polygon_payload())

    assert capture.observed_boundary.srid == 4326
    updated = update_site_capture(site_capture=capture, actor=owner, observed_boundary=None)

    assert updated.observed_boundary is None
    audit = AuditLog.objects.get(action=SITE_CAPTURE_UPDATED, entity_id=str(capture.pk))
    assert audit.after["changed_fields"] == ["observed_boundary"]


def test_geos_input_must_be_exact_type_and_srid_4326():
    owner, property_record = owner_and_property("GeosType")

    for point in (LineString((39.2, -6.7), (39.3, -6.8), srid=4326), Point(39.2, -6.7, srid=3857)):
        with pytest.raises(ValidationError):
            create_capture(owner, property_record, observed_point=point)

    for boundary in (
        Point(39.2, -6.7, srid=4326),
        MultiPolygon(Polygon(((39.2, -6.7), (39.3, -6.7), (39.2, -6.8), (39.2, -6.7)), srid=4326), srid=4326),
        Polygon(((39.2, -6.7), (39.3, -6.7), (39.2, -6.8), (39.2, -6.7)), srid=3857),
    ):
        with pytest.raises(ValidationError):
            create_capture(owner, property_record, observed_boundary=boundary)


def test_invalid_update_is_atomic_and_does_not_audit_or_change_property_or_verification():
    owner, property_record = owner_and_property("AtomicUpdate")
    capture = create_capture(owner, property_record, observed_boundary=polygon_payload())
    original_point = capture.observed_point.clone()
    original_boundary = capture.observed_boundary.clone()
    original_property_pin = property_record.pin.clone()
    initial_level = get_effective_verification_level(user=owner, property_record=property_record)

    with pytest.raises(ValidationError):
        update_site_capture(site_capture=capture, actor=owner, observed_point=point_payload(181, 0))

    capture.refresh_from_db()
    property_record.refresh_from_db()
    assert capture.observed_point.equals_exact(original_point, tolerance=0)
    assert capture.observed_boundary.equals_exact(original_boundary, tolerance=0)
    assert property_record.pin.equals_exact(original_property_pin, tolerance=0)
    assert get_effective_verification_level(user=owner, property_record=property_record) == initial_level
    assert not AuditLog.objects.filter(action=SITE_CAPTURE_UPDATED).exists()


def test_equivalent_geometry_is_a_noop_without_audit():
    owner, property_record = owner_and_property("SemanticNoop")
    capture = create_capture(owner, property_record, observed_boundary=polygon_payload())
    equivalent_boundary = {
        "type": "Polygon",
        "coordinates": [
            [[39.211, -6.789], [39.209, -6.791], [39.211, -6.791], [39.211, -6.789]],
        ],
    }

    updated = update_site_capture(
        site_capture=capture,
        actor=owner,
        observed_point=point_payload(),
        observed_boundary=equivalent_boundary,
    )

    assert updated.pk == capture.pk
    assert not AuditLog.objects.filter(action=SITE_CAPTURE_UPDATED).exists()


def test_audit_metadata_never_contains_geojson_or_geometry_values():
    owner, property_record = owner_and_property("AuditPrivacy")
    capture = create_capture(owner, property_record, observed_boundary=polygon_payload())
    update_site_capture(site_capture=capture, actor=owner, observed_point=point_payload(39.25, -6.75))

    serialized = " ".join(
        str(event.before) + str(event.after)
        for event in AuditLog.objects.filter(entity_type="SiteCapture", entity_id=str(capture.pk))
    )
    for forbidden in ("POINT", "POLYGON", "39.25", "-6.75", "coordinates", "GeoJSON"):
        assert forbidden not in serialized
