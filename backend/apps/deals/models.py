import uuid
from django.conf import settings
from django.db import models
from apps.common.models import TimeStampedModel


def payment_reference():
    return "OWR-" + uuid.uuid4().hex.upper()


class Deal(TimeStampedModel):
    lead = models.OneToOneField("leads.Lead", on_delete=models.PROTECT, related_name="deal")
    listing = models.ForeignKey("listings.Listing", on_delete=models.PROTECT, related_name="deals")
    property = models.ForeignKey("properties.PropertyRecord", on_delete=models.PROTECT)
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="buyer_deals")
    lister = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="lister_deals")
    buyer_name = models.CharField(max_length=255)
    buyer_whatsapp = models.CharField(max_length=30)
    lister_kind = models.CharField(max_length=16)
    owner_price = models.DecimalField(max_digits=18, decimal_places=0)
    final_selling_price = models.DecimalField(max_digits=18, decimal_places=0)
    rate_table = models.ForeignKey("commissions.RateTable", on_delete=models.PROTECT)
    rate_band = models.ForeignKey("commissions.RateBand", on_delete=models.PROTECT)
    total_rate = models.DecimalField(max_digits=7, decimal_places=6)
    oweru_rate = models.DecimalField(max_digits=7, decimal_places=6)
    buyer_to_owner = models.DecimalField(max_digits=18, decimal_places=0)
    buyer_to_oweru = models.DecimalField(max_digits=18, decimal_places=0)
    oweru_keeps = models.DecimalField(max_digits=18, decimal_places=0)
    agent_payout = models.DecimalField(max_digits=18, decimal_places=0)
    payment_reference = models.CharField(max_length=40, default=payment_reference, unique=True, editable=False)
    owner_bank_snapshot = models.JSONField(default=dict, editable=False)
    oweru_bank_snapshot = models.JSONField(default=dict, editable=False)
    state = models.CharField(max_length=16, default="OPEN")
    agreement = models.ForeignKey("media.Media", on_delete=models.PROTECT, null=True, blank=True)
    agreement_price_confirmed_at = models.DateTimeField(null=True, blank=True)
    agreement_approved_at = models.DateTimeField(null=True, blank=True)
    agreement_approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="approved_deal_agreements")
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(state__in=["OPEN", "COMPLETE", "CANCELLED"]), name="deal_state_valid"),
            models.UniqueConstraint(fields=["listing"], condition=models.Q(state="OPEN"), name="deal_one_open_listing"),
            models.CheckConstraint(condition=models.Q(final_selling_price__gt=0) & models.Q(owner_price__gt=0), name="deal_prices_positive"),
            models.CheckConstraint(condition=models.Q(buyer_to_owner__gte=0) & models.Q(buyer_to_oweru__gte=0) & models.Q(oweru_keeps__gte=0) & models.Q(agent_payout__gte=0), name="deal_money_nonnegative"),
            models.CheckConstraint(condition=models.Q(final_selling_price=models.F("buyer_to_owner") + models.F("buyer_to_oweru")), name="deal_transfers_reconcile"),
            models.CheckConstraint(condition=models.Q(buyer_to_oweru=models.F("oweru_keeps") + models.F("agent_payout")), name="deal_oweru_reconcile"),
        ]
        indexes = [models.Index(fields=["buyer", "state"], name="deal_buyer_state_idx"), models.Index(fields=["lister", "state"], name="deal_lister_state_idx")]
