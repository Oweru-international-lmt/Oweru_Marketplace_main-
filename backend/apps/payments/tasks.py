from celery import shared_task
from .services import mark_due_payouts

@shared_task
def payout_due_check():
    return mark_due_payouts()

@shared_task
def lost_sold_review():
    from apps.deals.models import Deal
    from apps.leads.services import review_lost_sales
    return sum(review_lost_sales(deal) for deal in Deal.objects.filter(state="COMPLETE").iterator())
