from django.core.management.base import BaseCommand, CommandError

from accounts.account_services import issue_phone_confirmation
from accounts.models import User


class Command(BaseCommand):
    help = (
        "Create a WhatsApp phone confirmation link for an account and print it (ACC-01). "
        "Stand-in until identity submission (M05) and the staff WhatsApp outbox (M21) send it."
    )

    def add_arguments(self, parser):
        parser.add_argument("--user-id", required=True)

    def handle(self, *args, **options):
        try:
            user = User.objects.get(pk=options["user_id"], is_active=True)
        except (User.DoesNotExist, ValueError):
            raise CommandError("No active account with that id.")
        confirmation, link = issue_phone_confirmation(user)
        self.stdout.write(f"Send this link to {user.phone} on WhatsApp (expires {confirmation.expires_at:%Y-%m-%d %H:%M}):")
        self.stdout.write(link)
