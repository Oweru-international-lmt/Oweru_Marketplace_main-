from django.conf import settings
from django.db import models
from apps.common.models import TimeStampedModel
from apps.verification.immutability import AppendOnly


class MessageTemplate(TimeStampedModel):
    key = models.CharField(max_length=64, unique=True)
    en = models.TextField()
    sw = models.TextField()
    version = models.PositiveIntegerField(default=1)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)


class TemplateHistory(AppendOnly, TimeStampedModel):
    template = models.ForeignKey(MessageTemplate, on_delete=models.PROTECT)
    version = models.PositiveIntegerField()
    en = models.TextField()
    sw = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["template", "version"], name="message_template_history_unique")]


class Notification(TimeStampedModel):
    CHANNELS = ["screen", "email", "outbox", "self_service"]
    event_key = models.CharField(max_length=200)
    purpose = models.CharField(max_length=64)
    channel = models.CharField(max_length=16)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="notifications")
    recipient_name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    language = models.CharField(max_length=2, default="sw")
    context = models.JSONField(default=dict)
    message = models.TextField()
    template_version = models.PositiveIntegerField(default=0)
    source_type = models.CharField(max_length=64, blank=True)
    source_id = models.UUIDField(null=True, blank=True)
    status = models.CharField(max_length=16, default="WAITING", db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    retry_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="created_notifications")
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="sent_notifications")
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["event_key", "channel"], name="notification_event_channel_unique"), models.CheckConstraint(condition=models.Q(channel__in=["screen", "email", "outbox", "self_service"]), name="notification_channel_valid"), models.CheckConstraint(condition=models.Q(status__in=["WAITING", "FAILED", "SENT", "CANCELLED"]), name="notification_status_valid")]


class DeliveryAttempt(AppendOnly, TimeStampedModel):
    notification = models.ForeignKey(Notification, on_delete=models.PROTECT, related_name="delivery_attempts")
    attempt = models.PositiveIntegerField()
    successful = models.BooleanField()
    error_type = models.CharField(max_length=100, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["notification", "attempt"], name="notification_attempt_unique")]
