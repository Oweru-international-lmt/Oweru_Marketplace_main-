import json
from json import JSONDecodeError
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.localities import services


class Command(BaseCommand):
    help = "Import controlled Region/District/Ward reference data from a UTF-8 JSON file."

    def add_arguments(self, parser):
        parser.add_argument("file", help="Path to a JSON file containing Region/District/Ward data.")

    def handle(self, *args, **options):
        path = Path(options["file"])
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            result = services.import_reference_localities(data)
        except FileNotFoundError as exc:
            raise CommandError(f"File not found: {path}") from exc
        except OSError as exc:
            raise CommandError(f"Unable to read file: {path}") from exc
        except JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON: {exc}") from exc
        except ValidationError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                "Import complete: "
                f"regions created={result['regions_created']}, existing={result['regions_existing']}; "
                f"districts created={result['districts_created']}, existing={result['districts_existing']}; "
                f"wards created={result['wards_created']}, existing={result['wards_existing']}"
            )
        )
