from celery import shared_task
from .services import refresh


@shared_task
def refresh_market_aggregates():
    return refresh()
