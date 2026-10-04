from decimal import Decimal
import uuid

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point, Polygon
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError

from apps.localities.models import District, Locality, Region, Ward
from apps.properties.models import PropertyRecord


pytestmark = pytest.mark.django_db


def create_user(email="property-creator@example.test"):
    return get_user_model().objects.create_user(
        email=email,
        phone=f"+255{abs(hash(email)) % 1000000000:09d}",
        full_name="Property Creator",
        password="StrongPass123!",
    )


def create_hierarchy(*, approved=True, prefix="Dar"):
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


def property_record_attrs(**overrides):
    region, district, ward, locality = create_hierarchy(
        approved=overrides.pop("approved", True),
        prefix=overrides.pop("prefix", "Base"),
    )
    attrs = {
        "property_id": "PROP-TEST-001",
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
        "created_by": create_user(),
    }
    attrs.update(overrides)
    return attrs


def create_property_record(**overrides):
    return PropertyRecord.objects.create(**property_record_attrs(**overrides))


def test_properties_app_loads_and_app_labels_are_unique():
    labels = [config.label for config in apps.get_app_configs()]

    assert apps.get_app_config("properties").name == "apps.properties"
    assert len(labels) == len(set(labels))


def test_property_record_creation_uuid_timestamps_and_string_representation():
    record = create_property_record()

    assert isinstance(record.pk, uuid.UUID)
    assert record.created_at is not None
    assert record.updated_at is not None
    assert str(record) == "PROP-TEST-001"
    assert str(record.pin.x) not in str(record)
    assert str(record.pin.y) not in str(record)


@pytest.mark.parametrize(
    "category",
    [
        PropertyRecord.Category.LAND,
        PropertyRecord.Category.HOUSE,
        PropertyRecord.Category.COMMERCIAL,
    ],
)
def test_documented_category_choices_are_accepted(category):
    record = PropertyRecord(**property_record_attrs(category=category))

    record.full_clean()


@pytest.mark.parametrize("category", ["APARTMENT", "OFFICE", "FARM", "OTHER"])
def test_undocumented_categories_are_rejected(category):
    record = PropertyRecord(**property_record_attrs(category=category))

    with pytest.raises(ValidationError):
        record.full_clean()


def test_missing_required_pin_rejected():
    record = PropertyRecord(**property_record_attrs(pin=None))

    with pytest.raises(ValidationError):
        record.full_clean()


def test_point_can_be_stored_with_srid_4326():
    record = create_property_record()

    assert record.pin.x == pytest.approx(39.2083)
    assert record.pin.y == pytest.approx(-6.7924)
    assert record.pin.srid == 4326


def test_polygon_boundary_can_be_stored_with_srid_4326():
    boundary = Polygon(((39.20, -6.79), (39.21, -6.79), (39.21, -6.80), (39.20, -6.80), (39.20, -6.79)), srid=4326)
    record = create_property_record(property_id="PROP-TEST-002", boundary=boundary, prefix="Poly")

    assert record.boundary is not None
    assert record.boundary.srid == 4326


def test_boundary_is_optional():
    record = PropertyRecord(**property_record_attrs(boundary=None))

    record.full_clean()


def test_invalid_locality_hierarchy_rejected():
    region, district, ward, locality = create_hierarchy(prefix="Valid")
    other_region, other_district, other_ward, other_locality = create_hierarchy(prefix="Other")
    record = PropertyRecord(
        **property_record_attrs(
            region=region,
            district=district,
            ward=ward,
            locality=other_locality,
            prefix="Hierarchy",
        )
    )

    with pytest.raises(ValidationError) as exc:
        record.full_clean()
    assert "locality" in exc.value.message_dict

    record.locality = locality
    record.ward = other_ward
    with pytest.raises(ValidationError) as exc:
        record.full_clean()
    assert "ward" in exc.value.message_dict

    record.ward = ward
    record.district = other_district
    with pytest.raises(ValidationError) as exc:
        record.full_clean()
    assert "district" in exc.value.message_dict

    assert other_region != region


@pytest.mark.parametrize("stated_size", [Decimal("0"), Decimal("-1.00")])
def test_non_positive_stated_size_rejected(stated_size):
    record = PropertyRecord(**property_record_attrs(stated_size=stated_size))

    with pytest.raises(ValidationError):
        record.full_clean()


@pytest.mark.parametrize(
    "title_type",
    [
        PropertyRecord.TitleType.REGISTERED_TITLE,
        PropertyRecord.TitleType.RESIDENTIAL_LICENCE,
        PropertyRecord.TitleType.SALE_AGREEMENT,
        PropertyRecord.TitleType.CCRO,
        PropertyRecord.TitleType.VILLAGE_RECORDS,
        PropertyRecord.TitleType.NONE,
        PropertyRecord.TitleType.UNKNOWN,
    ],
)
def test_documented_title_type_choices_are_accepted(title_type):
    record = PropertyRecord(**property_record_attrs(title_type=title_type))

    record.full_clean()


def test_invalid_title_type_rejected():
    record = PropertyRecord(**property_record_attrs(title_type="TITLE_DEED"))

    with pytest.raises(ValidationError):
        record.full_clean()


def test_property_id_is_unique():
    create_property_record(property_id="PROP-UNIQUE-001")

    with pytest.raises(IntegrityError), transaction.atomic():
        create_property_record(property_id="PROP-UNIQUE-001", prefix="Duplicate")


def test_pending_locality_is_allowed_at_model_level():
    record = PropertyRecord(**property_record_attrs(approved=False))

    record.full_clean()


def test_parent_locality_and_creator_deletion_are_protected():
    record = create_property_record()

    with pytest.raises(ProtectedError):
        record.region.delete()
    with pytest.raises(ProtectedError):
        record.district.delete()
    with pytest.raises(ProtectedError):
        record.ward.delete()
    with pytest.raises(ProtectedError):
        record.locality.delete()
    with pytest.raises(ProtectedError):
        record.created_by.delete()


def test_property_record_does_not_contain_listing_or_future_domain_fields():
    fields = {field.name for field in PropertyRecord._meta.get_fields()}

    assert {
        "price",
        "selling_price",
        "owner_price",
        "currency",
        "description",
        "features",
        "listing_status",
        "published_at",
        "promoted",
        "is_promoted",
        "lister_kind",
        "owner_contact",
        "owner_bank",
        "verification_level",
        "document",
        "document_ref",
        "file",
        "file_ref",
        "lister_identity",
        "owner",
        "agent",
        "lister",
    }.isdisjoint(fields)


def test_no_listing_model_exists_in_m06b():
    model_names = {model.__name__ for model in apps.get_models()}

    assert "Listing" not in model_names
