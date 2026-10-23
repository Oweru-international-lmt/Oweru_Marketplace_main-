from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.administration import examples
from apps.audit.services import create_audit_log
from apps.commissions.models import RateBand, RateTable
from apps.verification.models import VerificationSetting


class Command(BaseCommand):
    help = "Decision D5: seed the example commission table and full check fee where none exist yet. Safe to run again."

    @transaction.atomic
    def handle(self, *args, **options):
        if not RateTable.objects.exists():
            table = RateTable.objects.create(version=1, total_rate=examples.TOTAL_RATE)
            for lower, upper, oweru, agent in examples.RATE_BANDS:
                RateBand.objects.create(table=table, lower=lower, upper=upper, oweru_rate=oweru, agent_rate=agent)
            RateTable.objects.filter(pk=table.pk).update(published_at=timezone.now())
            create_audit_log(action="rate_table.example_seeded", entity_type="RateTable", entity_id=table.pk, after={"version": 1, "published": True})
            self.stdout.write("Published the example commission table as version 1.")
        elif not RateTable.objects.filter(published_at__isnull=True).exists() and not self._matches_current():
            version = (RateTable.objects.aggregate(top=Max("version"))["top"] or 0) + 1
            table = RateTable.objects.create(version=version, total_rate=examples.TOTAL_RATE)
            for lower, upper, oweru, agent in examples.RATE_BANDS:
                RateBand.objects.create(table=table, lower=lower, upper=upper, oweru_rate=oweru, agent_rate=agent)
            create_audit_log(action="rate_table.example_seeded", entity_type="RateTable", entity_id=table.pk, after={"version": version, "published": False})
            self.stdout.write(f"A table is already published; the example is saved as draft version {version} for Management to review.")
        else:
            self.stdout.write("Commission table left as it is.")

        if not VerificationSetting.objects.filter(key="full_check_fee").exists():
            row = VerificationSetting.objects.create(key="full_check_fee", value=str(examples.FULL_CHECK_FEE), version=1)
            create_audit_log(action="verification.setting_example_seeded", entity_type="VerificationSetting", entity_id=row.pk, after={"key": "full_check_fee", "value": row.value})
            self.stdout.write(f"Full check fee set to the example TSh {examples.FULL_CHECK_FEE:,}.")
        else:
            self.stdout.write("Full check fee left as it is.")

    def _matches_current(self):
        from apps.commissions.services import current_rate_table
        table = current_rate_table()
        if table is None:
            return False
        bands = [(band.lower, band.upper, band.oweru_rate, band.agent_rate) for band in table.bands.order_by("lower")]
        return bands == list(examples.RATE_BANDS)
