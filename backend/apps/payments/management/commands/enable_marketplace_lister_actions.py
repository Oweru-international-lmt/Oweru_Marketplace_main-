from uuid import UUID
from django.core.management.base import BaseCommand, CommandError
from rest_framework.exceptions import APIException
from apps.accounts.models import User
from apps.payments.onboarding import enable_lister_actions


class Command(BaseCommand):
    help = "Explicitly enable verified Marketplace lister actions in the permission-bearing store."

    def add_arguments(self, parser):
        parser.add_argument("--manager-id", required=True)
        parser.add_argument("--lister-id", required=True)
        parser.add_argument("--role", required=True, choices=["owner", "agent"])

    def handle(self, *args, **options):
        try:
            actor = User.objects.get(pk=UUID(options["manager_id"]))
            assignment = enable_lister_actions(actor=actor, user_id=UUID(options["lister_id"]), role_code=options["role"])
        except (User.DoesNotExist, ValueError, APIException) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Marketplace lister actions enabled: {assignment.pk}"))
