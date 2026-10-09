from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.accounts.models import User
from apps.administration.services import history


class Command(BaseCommand):
    help = "Trusted deployment setup only: designate existing Management as Director or Head of Operations."

    def add_arguments(self, parser):
        parser.add_argument("email")
        parser.add_argument("position", choices=["DIRECTOR", "HEAD_OPERATIONS"])
        parser.add_argument("--setup-actor", required=True, help="Existing active Django superuser email")
        parser.add_argument("--reason", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        rows = list(User.objects.select_for_update().filter(email__in=[options["email"].lower(), options["setup_actor"].lower()]).order_by("pk"))
        actor = next((row for row in rows if row.email == options["setup_actor"].lower()), None)
        user = next((row for row in rows if row.email == options["email"].lower()), None)
        if actor is None or not actor.is_active or not actor.is_superuser or user is None or not user.has_role("management"):
            raise CommandError("An active trusted setup superuser and existing Management target are required.")
        before = {"management_position": user.management_position}
        user.management_position = options["position"]
        user.administration_version += 1
        user.save(update_fields=["management_position", "administration_version", "updated_at"])
        history(actor, user, options["reason"], before, {"management_position": user.management_position})
        self.stdout.write("Management office designated; no new role or action grant created.")
