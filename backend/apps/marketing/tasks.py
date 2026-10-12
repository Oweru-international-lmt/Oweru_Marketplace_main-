from celery import shared_task
from django.db.models import Q
from django.utils import timezone
from .models import CampaignDelivery
from .services import deliver


@shared_task
def deliver_campaigns():
    identifiers = list(CampaignDelivery.objects.filter(status="WAITING").filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=timezone.now())).order_by("created_at").values_list("pk", flat=True)[:100])
    for identifier in identifiers:
        deliver(identifier)
    return len(identifiers)
