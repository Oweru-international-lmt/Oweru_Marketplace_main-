import pytest
from django.core.exceptions import ValidationError

from apps.localities.models import District, Locality, Region, Ward
from apps.localities.services import import_reference_localities


pytestmark = pytest.mark.django_db


def payload():
    return [
        {
            "name": "Synthetic Region A",
            "districts": [
                {
                    "name": "Synthetic District A1",
                    "wards": [
                        {"name": "Synthetic Ward A1a"},
                        {"name": "Synthetic Ward A1b"},
                    ],
                },
                {
                    "name": "Synthetic District A2",
                    "wards": [{"name": "Synthetic Ward A2a"}],
                },
            ],
        },
        {
            "name": "Synthetic Region B",
            "districts": [
                {
                    "name": "Synthetic District B1",
                    "wards": [{"name": "Synthetic Ward B1a"}],
                }
            ],
        },
    ]


def test_valid_hierarchy_imports():
    result = import_reference_localities(payload())

    assert result == {
        "regions_created": 2,
        "districts_created": 3,
        "wards_created": 4,
        "regions_existing": 0,
        "districts_existing": 0,
        "wards_existing": 0,
    }
    assert Region.objects.count() == 2
    assert District.objects.count() == 3
    assert Ward.objects.count() == 4


def test_second_identical_import_is_idempotent():
    import_reference_localities(payload())

    result = import_reference_localities(payload())

    assert result["regions_created"] == 0
    assert result["districts_created"] == 0
    assert result["wards_created"] == 0
    assert result["regions_existing"] == 2
    assert result["districts_existing"] == 3
    assert result["wards_existing"] == 4
    assert Region.objects.count() == 2
    assert District.objects.count() == 3
    assert Ward.objects.count() == 4


def test_case_only_duplicates_are_matched():
    import_reference_localities(
        [
            {
                "name": "Synthetic Region",
                "districts": [
                    {"name": "Synthetic District", "wards": [{"name": "Synthetic Ward"}]},
                ],
            }
        ]
    )

    result = import_reference_localities(
        [
            {
                "name": "synthetic region",
                "districts": [
                    {"name": "synthetic district", "wards": [{"name": "synthetic ward"}]},
                ],
            }
        ]
    )

    assert result["regions_existing"] == 1
    assert result["districts_existing"] == 1
    assert result["wards_existing"] == 1
    assert Region.objects.count() == 1
    assert District.objects.count() == 1
    assert Ward.objects.count() == 1


def test_whitespace_normalization_works():
    import_reference_localities(
        [
            {
                "name": "  Synthetic Region  ",
                "districts": [
                    {"name": "  Synthetic District  ", "wards": [{"name": "  Synthetic Ward  "}]},
                ],
            }
        ]
    )

    assert Region.objects.get().name == "Synthetic Region"
    assert District.objects.get().name == "Synthetic District"
    assert Ward.objects.get().name == "Synthetic Ward"


def test_existing_data_preserved_and_missing_data_added():
    region = Region.objects.create(name="Synthetic Region")
    district = District.objects.create(region=region, name="Synthetic District")
    Ward.objects.create(district=district, name="Synthetic Existing Ward")

    result = import_reference_localities(
        [
            {
                "name": "Synthetic Region",
                "districts": [
                    {
                        "name": "Synthetic District",
                        "wards": [
                            {"name": "Synthetic Existing Ward"},
                            {"name": "Synthetic New Ward"},
                        ],
                    },
                    {"name": "Synthetic New District", "wards": [{"name": "Synthetic New District Ward"}]},
                ],
            }
        ]
    )

    assert result["regions_existing"] == 1
    assert result["districts_existing"] == 1
    assert result["wards_existing"] == 1
    assert result["districts_created"] == 1
    assert result["wards_created"] == 2
    assert Region.objects.get(pk=region.pk).name == "Synthetic Region"
    assert District.objects.filter(region=region).count() == 2
    assert Ward.objects.count() == 3


def test_locality_records_are_untouched():
    region = Region.objects.create(name="Synthetic Region")
    district = District.objects.create(region=region, name="Synthetic District")
    ward = Ward.objects.create(district=district, name="Synthetic Ward")
    locality = Locality.objects.create(ward=ward, name="Synthetic Street", kind=Locality.Kind.STREET)

    import_reference_localities(
        [
            {
                "name": "Synthetic Region",
                "districts": [
                    {"name": "Synthetic District", "wards": [{"name": "Synthetic Ward"}]},
                ],
            }
        ]
    )

    locality.refresh_from_db()
    assert locality.name == "Synthetic Street"
    assert Locality.objects.count() == 1


@pytest.mark.parametrize(
    "bad_data",
    [
        {"name": "Synthetic Region"},
        [{"districts": []}],
        [{"name": "   ", "districts": []}],
        [{"name": "Synthetic Region", "districts": [{"wards": []}]}],
        [{"name": "Synthetic Region", "districts": [{"name": " ", "wards": []}]}],
        [{"name": "Synthetic Region", "districts": [{"name": "Synthetic District", "wards": [{}]}]}],
        [{"name": "Synthetic Region", "districts": [{"name": "Synthetic District", "wards": [{"name": " "}]}]}],
        [{"name": "Synthetic Region", "districts": "Synthetic District"}],
        [{"name": "Synthetic Region", "districts": [{"name": "Synthetic District", "wards": "Synthetic Ward"}]}],
    ],
)
def test_malformed_import_data_rejected(bad_data):
    with pytest.raises(ValidationError):
        import_reference_localities(bad_data)


def test_invalid_hierarchy_leaves_no_partial_reference_data():
    with pytest.raises(ValidationError):
        import_reference_localities(
            [
                {
                    "name": "Synthetic Region",
                    "districts": [
                        {"name": "Synthetic District", "wards": [{"name": "Synthetic Ward"}]},
                        {"name": "Broken District", "wards": [{"name": " "}]},
                    ],
                }
            ]
        )

    assert Region.objects.count() == 0
    assert District.objects.count() == 0
    assert Ward.objects.count() == 0
