from decimal import Decimal
import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.site_capture.services import create_site_capture, record_corner, submit_site_capture, require_full_check_capture
from .test_models_services import make_owner_and_property

pytestmark = pytest.mark.django_db


def capture_fixture():
    owner, property_record = make_owner_and_property("Measured")
    capture = create_site_capture(actor=owner, property_record=property_record, observed_point=property_record.pin)
    return owner, property_record, capture


def test_one_point_without_boundary_cannot_be_submitted():
    owner, _, capture = capture_fixture()
    with pytest.raises(ValidationError):
        submit_site_capture(actor=owner, site_capture=capture)
    capture.refresh_from_db()
    assert capture.status == "DRAFT"


def test_corner_accuracy_limit_and_minimum_three_are_enforced():
    owner, _, capture = capture_fixture()
    with pytest.raises(ValidationError):
        record_corner(actor=owner, site_capture=capture, point=capture.observed_point, accuracy_m=10.01, observed_at=timezone.now(), device="phone")
    record_corner(actor=owner, site_capture=capture, point=capture.observed_point, accuracy_m=10, observed_at=timezone.now(), device="phone")
    with pytest.raises(ValidationError):
        submit_site_capture(actor=owner, site_capture=capture)


def test_postgis_measures_corners_and_locks_submission():
    owner, property_record, capture = capture_fixture()
    for lon, lat in [(39.2083, -6.7924), (39.2086, -6.7924), (39.2086, -6.7921), (39.2083, -6.7921)]:
        record_corner(actor=owner, site_capture=capture, point=Point(lon, lat, srid=4326), accuracy_m=5, observed_at=timezone.now(), device="phone")
    capture = submit_site_capture(actor=owner, site_capture=capture)
    assert Decimal(900) < capture.measured_area_sqm < Decimal(1200)
    assert capture.area_difference_percent is not None
    assert capture.observed_boundary.srid == 4326
    require_full_check_capture(capture, property_record)
    with pytest.raises(ValidationError):
        record_corner(actor=owner, site_capture=capture, point=capture.observed_point, accuracy_m=5, observed_at=timezone.now(), device="phone")
