import json
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.localities.models import District, Region, Ward


pytestmark = pytest.mark.django_db


def write_json(tmp_path, data):
    path = tmp_path / "localities.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def command_payload():
    return [
        {
            "name": "Synthetic Region",
            "districts": [
                {"name": "Synthetic District", "wards": [{"name": "Synthetic Ward"}]},
            ],
        }
    ]


def test_valid_json_imports_successfully(tmp_path):
    path = write_json(tmp_path, command_payload())
    out = StringIO()

    call_command("import_localities", str(path), stdout=out)

    assert "Import complete" in out.getvalue()
    assert Region.objects.count() == 1
    assert District.objects.count() == 1
    assert Ward.objects.count() == 1


def test_invalid_json_fails(tmp_path):
    path = tmp_path / "localities.json"
    path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(CommandError):
        call_command("import_localities", str(path))


def test_nonexistent_file_fails(tmp_path):
    with pytest.raises(CommandError):
        call_command("import_localities", str(tmp_path / "missing.json"))


def test_malformed_structure_fails(tmp_path):
    path = write_json(tmp_path, {"name": "Synthetic Region"})

    with pytest.raises(CommandError):
        call_command("import_localities", str(path))


def test_repeated_command_is_idempotent(tmp_path):
    path = write_json(tmp_path, command_payload())

    call_command("import_localities", str(path))
    call_command("import_localities", str(path))

    assert Region.objects.count() == 1
    assert District.objects.count() == 1
    assert Ward.objects.count() == 1


def test_command_delegates_to_canonical_import_service(tmp_path):
    path = write_json(tmp_path, command_payload())

    with patch("apps.localities.management.commands.import_localities.services.import_reference_localities") as import_service:
        import_service.return_value = {
            "regions_created": 0,
            "districts_created": 0,
            "wards_created": 0,
            "regions_existing": 1,
            "districts_existing": 1,
            "wards_existing": 1,
        }
        call_command("import_localities", str(path))

    import_service.assert_called_once_with(command_payload())
