from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from rest_framework.exceptions import APIException
from accounts.models import User
from authorization.services import bootstrap_management


class Command(BaseCommand):
    help = "Assign Marketplace Management to an existing operational Django superuser (trusted setup only)."

    def add_arguments(self, parser):
        parser.add_argument("--user-id", required=True)

    def handle(self, *args, **options):
        try:
            user = User.objects.get(pk=options["user_id"])
            bootstrap_management(user=user)
        except (User.DoesNotExist, APIException, ValueError, ValidationError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS("Marketplace Management assigned; audit recorded for changes."))
