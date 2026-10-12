from django.conf import settings
from django.db import models
from apps.common.models import TimeStampedModel
from apps.verification.immutability import AppendOnly


class MarketingConsent(TimeStampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    agreed = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)


class ConsentHistory(AppendOnly, TimeStampedModel):
    consent = models.ForeignKey(MarketingConsent, on_delete=models.PROTECT)
    agreed = models.BooleanField()
    version = models.PositiveIntegerField()
    policy_version = models.CharField(max_length=100)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["consent", "version"], name="marketing_consent_history_unique")]


class FeaturedListing(TimeStampedModel):
    listing = models.ForeignKey("listings.Listing", on_delete=models.PROTECT)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    enabled = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(ends_at__gt=models.F("starts_at")), name="featured_period_valid")]
        indexes = [models.Index(fields=["enabled", "starts_at", "ends_at"], name="featured_period_idx")]


class Content(TimeStampedModel):
    slug = models.SlugField(unique=True)
    kind = models.CharField(max_length=10, choices=[("BANNER", "Banner"), ("PAGE", "Page")])
    title_en = models.CharField(max_length=200)
    title_sw = models.CharField(max_length=200)
    body_en = models.TextField()
    body_sw = models.TextField()
    target_path = models.CharField(max_length=500)
    source_tag = models.SlugField(max_length=100)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    enabled = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(ends_at__gt=models.F("starts_at")), name="marketing_content_period_valid"), models.CheckConstraint(condition=models.Q(kind__in=["BANNER", "PAGE"]), name="marketing_content_kind_valid")]


class Campaign(AppendOnly, TimeStampedModel):
    subject_en = models.CharField(max_length=200)
    subject_sw = models.CharField(max_length=200)
    body_en = models.TextField()
    body_sw = models.TextField()
    target_path = models.CharField(max_length=500)
    source_tag = models.SlugField(max_length=100, unique=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)


class CampaignDelivery(TimeStampedModel):
    campaign = models.ForeignKey(Campaign, on_delete=models.PROTECT, related_name="deliveries")
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    status = models.CharField(max_length=10, default="WAITING")
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True)
    sent_at = models.DateTimeField(null=True)
    clicked_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["campaign", "recipient"], name="campaign_recipient_unique"), models.CheckConstraint(condition=models.Q(status__in=["WAITING", "SENT", "FAILED", "CANCELLED"]), name="campaign_delivery_status_valid")]
        indexes = [models.Index(fields=["status", "next_attempt_at"], name="campaign_pending_idx")]


class CampaignAttempt(AppendOnly, TimeStampedModel):
    delivery = models.ForeignKey(CampaignDelivery, on_delete=models.PROTECT)
    success = models.BooleanField()
    error_type = models.CharField(max_length=100, blank=True)
