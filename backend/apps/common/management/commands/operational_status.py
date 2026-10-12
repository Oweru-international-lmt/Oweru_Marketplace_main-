import json
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone
from apps.analytics.models import AggregateRun
from apps.marketing.models import CampaignDelivery
from apps.notifications.models import Notification
from apps.notifications.services import working_hours
from apps.verification.configuration import setting


def status():
    now = timezone.now()
    latest = AggregateRun.objects.order_by("-completed_at").first()
    waiting = Notification.objects.filter(channel="outbox", status="WAITING").filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now)).filter(Q(recipient__isnull=True) | Q(recipient__is_active=True)).order_by("created_at")
    dates = list(waiting.values_list("created_at", flat=True)[:1000])
    return {"analytics_stale": latest is None or (now - latest.completed_at).total_seconds() > 26 * 3600, "analytics_refreshed_at": latest.completed_at.isoformat() if latest else None, "failed_transactional_emails": Notification.objects.filter(channel="email", status="FAILED").count(), "failed_campaign_emails": CampaignDelivery.objects.filter(status="FAILED").count(), "outbox_waiting": waiting.count(), "overdue_outbox_in_oldest_1000": sum(working_hours(value, now) >= float(setting("outbox_waiting_hours")) for value in dates), "outbox_sample_limit": 1000}


class Command(BaseCommand):
    help = "Read-only bounded non-personal operational counters for monitoring ingestion."

    def handle(self, **options):
        self.stdout.write(json.dumps(status(), sort_keys=True))
