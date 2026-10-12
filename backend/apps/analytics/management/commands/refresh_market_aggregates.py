from django.core.management.base import BaseCommand
from apps.analytics.services import refresh


class Command(BaseCommand):
    help = "Refresh non-personal market aggregates without sending messages."

    def handle(self, **options):
        self.stdout.write(f"Refreshed {refresh()} aggregate cells.")
