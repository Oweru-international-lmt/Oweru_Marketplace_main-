from django.core.management.base import BaseCommand
from django.db import transaction
from apps.verification.models import VerificationNotice
from apps.payments.models import FinancialNotice, ConfirmationDelivery
from apps.complaints.models import ComplaintNotice
from apps.free_checks.models import FreeCheckReport
from apps.notifications.signals import verification_notice, financial_notice, confirmation, complaint_notice, free_report


class Command(BaseCommand):
    help = "Idempotently import existing durable notification intents; sends no messages."

    def handle(self, *args, **options):
        count = 0
        for model, handler in [(VerificationNotice, verification_notice), (FinancialNotice, financial_notice), (ConfirmationDelivery, confirmation), (ComplaintNotice, complaint_notice), (FreeCheckReport, free_report)]:
            for row in model.objects.all().iterator():
                with transaction.atomic():
                    handler(model, row, True)
                    if model in {VerificationNotice, ConfirmationDelivery}:
                        handler(model, row, False)
                count += 1
        self.stdout.write(f"Reconciled {count} durable intents; no delivery performed.")
