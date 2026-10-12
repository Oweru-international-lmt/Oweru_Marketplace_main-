from django.db import models
from apps.common.models import TimeStampedModel
from apps.verification.immutability import AppendOnly


class MarketEvent(AppendOnly, TimeStampedModel):
    kind = models.CharField(max_length=10, choices=[("SEARCH", "Search"), ("VIEW", "View"), ("ENQUIRY", "Enquiry")])
    region = models.UUIDField(null=True)
    district = models.UUIDField(null=True)
    ward = models.UUIDField(null=True)
    category = models.CharField(max_length=20, blank=True)
    price_range = models.CharField(max_length=50, blank=True)
    filters = models.JSONField(default=list)
    source_tag = models.SlugField(max_length=100, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(kind__in=["SEARCH", "VIEW", "ENQUIRY"]), name="market_event_kind_valid")]
        indexes = [models.Index(fields=["kind", "created_at"], name="market_event_kind_date_idx"), models.Index(fields=["region", "district", "category", "created_at"], name="market_event_area_date_idx")]


class LeadAttribution(AppendOnly, TimeStampedModel):
    lead = models.OneToOneField("leads.Lead", on_delete=models.PROTECT)
    source_tag = models.SlugField(max_length=100, blank=True)


class DealPriceSnapshot(AppendOnly, TimeStampedModel):
    deal = models.OneToOneField("deals.Deal", on_delete=models.PROTECT)
    listed_price = models.DecimalField(max_digits=18, decimal_places=0)


class MarketAggregate(TimeStampedModel):
    day = models.DateField()
    kind = models.CharField(max_length=10)
    area_key = models.CharField(max_length=150)
    region = models.UUIDField(null=True)
    district = models.UUIDField(null=True)
    ward = models.UUIDField(null=True)
    category = models.CharField(max_length=20, blank=True)
    metrics = models.JSONField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["day", "kind", "area_key"], name="market_aggregate_cell_unique")]
        indexes = [models.Index(fields=["kind", "day", "region", "district", "category"], name="market_aggregate_filter_idx")]


class AggregateRun(TimeStampedModel):
    completed_at = models.DateTimeField()
    cells = models.PositiveIntegerField()
