import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError

from apps.localities.models import District, Locality, Region, Ward
from apps.roles.catalog import CANONICAL_ROLE_CODES
from apps.roles.models import Role
from apps.roles.services import bootstrap_canonical_roles


pytestmark = pytest.mark.django_db


def create_user(email="creator@example.test"):
    return get_user_model().objects.create_user(
        email=email,
        phone=f"+255{abs(hash(email)) % 1000000000:09d}",
        full_name="Locality Creator",
        password="StrongPass123!",
    )


def create_hierarchy():
    region = Region.objects.create(name="Dar es Salaam")
    district = District.objects.create(region=region, name="Kinondoni")
    ward = Ward.objects.create(district=district, name="Msasani")
    return region, district, ward


def assert_unique_violation(callback):
    with pytest.raises(IntegrityError), transaction.atomic():
        callback()


def test_region_creation_normalizes_name():
    region = Region.objects.create(name="  Dar es Salaam  ")

    assert region.name == "Dar es Salaam"


def test_region_blank_name_rejected():
    region = Region(name="   ")

    with pytest.raises(ValidationError):
        region.full_clean()


def test_region_duplicate_name_rejected_case_insensitive():
    Region.objects.create(name="Dar es Salaam")

    assert_unique_violation(lambda: Region.objects.create(name="dar es salaam"))


def test_district_requires_region():
    district = District(name="Kinondoni")

    with pytest.raises(ValidationError):
        district.full_clean()


def test_district_duplicate_name_within_region_rejected_case_insensitive():
    region = Region.objects.create(name="Dar es Salaam")
    District.objects.create(region=region, name="Kinondoni")

    assert_unique_violation(lambda: District.objects.create(region=region, name="kinondoni"))


def test_district_same_name_under_different_regions_allowed():
    dar = Region.objects.create(name="Dar es Salaam")
    pwani = Region.objects.create(name="Pwani")

    District.objects.create(region=dar, name="Kibaha")
    district = District.objects.create(region=pwani, name="kibaha")

    assert district.region == pwani


def test_ward_requires_district():
    ward = Ward(name="Msasani")

    with pytest.raises(ValidationError):
        ward.full_clean()


def test_ward_duplicate_name_within_district_rejected_case_insensitive():
    _, district, _ = create_hierarchy()
    Ward.objects.create(district=district, name="Oyster Bay")

    assert_unique_violation(lambda: Ward.objects.create(district=district, name="oyster bay"))


def test_ward_same_name_under_different_districts_allowed():
    region = Region.objects.create(name="Dar es Salaam")
    kinondoni = District.objects.create(region=region, name="Kinondoni")
    ilala = District.objects.create(region=region, name="Ilala")

    Ward.objects.create(district=kinondoni, name="Upanga")
    ward = Ward.objects.create(district=ilala, name="upanga")

    assert ward.district == ilala


def test_locality_requires_ward():
    locality = Locality(name="Mikocheni B", kind=Locality.Kind.STREET)

    with pytest.raises(ValidationError):
        locality.full_clean()


def test_locality_valid_kinds_and_default_approval():
    _, _, ward = create_hierarchy()

    street = Locality.objects.create(ward=ward, name="Mikocheni B", kind=Locality.Kind.STREET)
    village = Locality.objects.create(ward=ward, name="Kijiji", kind=Locality.Kind.VILLAGE)

    assert street.kind == "street"
    assert village.kind == "village"
    assert street.approved is False


def test_locality_invalid_kind_rejected():
    _, _, ward = create_hierarchy()
    locality = Locality(ward=ward, name="Mikocheni B", kind="area")

    with pytest.raises(ValidationError):
        locality.full_clean()


def test_locality_blank_name_rejected():
    _, _, ward = create_hierarchy()
    locality = Locality(ward=ward, name="  ", kind=Locality.Kind.STREET)

    with pytest.raises(ValidationError):
        locality.full_clean()


def test_locality_duplicate_ward_kind_name_rejected_case_insensitive():
    _, _, ward = create_hierarchy()
    Locality.objects.create(ward=ward, name="Mikocheni B", kind=Locality.Kind.STREET)

    assert_unique_violation(
        lambda: Locality.objects.create(ward=ward, name="mikocheni b", kind=Locality.Kind.STREET)
    )


def test_locality_same_name_with_different_kind_allowed():
    _, _, ward = create_hierarchy()

    Locality.objects.create(ward=ward, name="Mikocheni", kind=Locality.Kind.STREET)
    locality = Locality.objects.create(ward=ward, name="mikocheni", kind=Locality.Kind.VILLAGE)

    assert locality.kind == Locality.Kind.VILLAGE


def test_locality_same_name_and_kind_under_different_wards_allowed():
    region = Region.objects.create(name="Dar es Salaam")
    district = District.objects.create(region=region, name="Kinondoni")
    msasani = Ward.objects.create(district=district, name="Msasani")
    kawe = Ward.objects.create(district=district, name="Kawe")

    Locality.objects.create(ward=msasani, name="Mikocheni B", kind=Locality.Kind.STREET)
    locality = Locality.objects.create(ward=kawe, name="mikocheni b", kind=Locality.Kind.STREET)

    assert locality.ward == kawe


def test_locality_hierarchy_navigation_works():
    region, district, ward = create_hierarchy()
    locality = Locality.objects.create(ward=ward, name="Mikocheni B", kind=Locality.Kind.STREET)

    assert locality.ward.district.region == region
    assert list(region.districts.all()) == [district]
    assert list(district.wards.all()) == [ward]
    assert list(ward.localities.all()) == [locality]


def test_locality_created_by_can_be_user_or_system():
    _, _, ward = create_hierarchy()
    user = create_user()

    user_locality = Locality.objects.create(
        ward=ward,
        name="User Submitted",
        kind=Locality.Kind.STREET,
        created_by=user,
    )
    system_locality = Locality.objects.create(ward=ward, name="System Imported", kind=Locality.Kind.VILLAGE)

    assert user_locality.created_by == user
    assert system_locality.created_by is None


def test_parent_deletion_is_protected_when_children_exist():
    region, district, ward = create_hierarchy()
    Locality.objects.create(ward=ward, name="Mikocheni B", kind=Locality.Kind.STREET)

    with pytest.raises(ProtectedError):
        region.delete()
    with pytest.raises(ProtectedError):
        district.delete()
    with pytest.raises(ProtectedError):
        ward.delete()


def test_canonical_roles_are_unaffected_by_localities_app():
    bootstrap_canonical_roles()

    assert set(Role.objects.filter(code__in=CANONICAL_ROLE_CODES).values_list("code", flat=True)) == set(
        CANONICAL_ROLE_CODES
    )
