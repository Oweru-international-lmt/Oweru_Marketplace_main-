from django.conf import settings
from django.db import models
from apps.common.models import TimeStampedModel


class Lead(TimeStampedModel):
    class Stage(models.TextChoices):
        NEW = "NEW"
        CONTACTED = "CONTACTED"
        VIEWING = "VIEWING"
        NEGOTIATION = "NEGOTIATION"
        CLOSING = "CLOSING"
        WON = "WON"
        LOST = "LOST"

    class Source(models.TextChoices):
        ENQUIRY = "ENQUIRY"
        WHATSAPP_CONTACT = "WHATSAPP_CONTACT"
        VIEWING_REQUEST = "VIEWING_REQUEST"

    listing = models.ForeignKey("listings.Listing", on_delete=models.PROTECT, related_name="leads")
    property = models.ForeignKey("properties.PropertyRecord", on_delete=models.PROTECT, related_name="leads")
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="buyer_leads")
    lister = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="lister_leads")
    buyer_name = models.CharField(max_length=255)
    buyer_whatsapp = models.CharField(max_length=30)
    source = models.CharField(max_length=24, choices=Source.choices)
    stage = models.CharField(max_length=16, choices=Stage.choices, default=Stage.NEW)
    follow_up_at = models.DateTimeField(null=True, blank=True)
    lost_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(stage__in=["NEW", "CONTACTED", "VIEWING", "NEGOTIATION", "CLOSING", "WON", "LOST"]), name="lead_stage_valid"),
            models.CheckConstraint(condition=models.Q(source__in=["ENQUIRY", "WHATSAPP_CONTACT", "VIEWING_REQUEST"]), name="lead_source_valid"),
            models.CheckConstraint(condition=~models.Q(buyer_name="") & ~models.Q(buyer_whatsapp=""), name="lead_contact_required"),
        ]
        indexes = [models.Index(fields=["lister", "stage", "follow_up_at"], name="lead_lister_pipeline_idx"), models.Index(fields=["property", "buyer", "lost_at"], name="lead_lost_buyer_idx")]


class LeadTransition(TimeStampedModel):
    lead = models.ForeignKey(Lead, on_delete=models.PROTECT, related_name="transitions")
    from_stage = models.CharField(max_length=16)
    to_stage = models.CharField(max_length=16)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.TextField(blank=True)


class LeadNote(TimeStampedModel):
    lead = models.ForeignKey(Lead, on_delete=models.PROTECT, related_name="notes")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    text = models.TextField()


class LostLeadReview(TimeStampedModel):
    lost_lead = models.ForeignKey(Lead, on_delete=models.PROTECT, related_name="sale_reviews")
    sold_deal = models.ForeignKey("deals.Deal", on_delete=models.PROTECT, related_name="lost_lead_reviews")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["lost_lead", "sold_deal"], name="lost_sale_review_unique")]
