import secrets
from django.conf import settings
from django.db import models
from apps.common.models import TimeStampedModel
from apps.verification.immutability import AppendOnly


def number():
    return "CMP-" + secrets.token_hex(8).upper()


class Complaint(TimeStampedModel):
    TYPES = ["FAKE_LISTING", "WRONG_LISTING", "CONDUCT", "PAYMENT", "PAYOUT", "PRIVACY", "VERIFICATION", "OTHER"]
    STATUSES = ["RECEIVED", "IN_REVIEW", "WAITING_INFORMATION", "RESOLVED", "UNDER_FINAL_REVIEW", "CLOSED"]
    reference = models.CharField(max_length=30, unique=True, default=number)
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    complainant_role = models.CharField(max_length=30)
    category = models.CharField(max_length=20, choices=[(v, v) for v in TYPES])
    source = models.CharField(max_length=10, choices=[(v, v) for v in ["WEB", "WHATSAPP", "EMAIL"]])
    language = models.CharField(max_length=2, default="sw")
    description = models.TextField()
    property = models.ForeignKey("properties.PropertyRecord", on_delete=models.PROTECT, null=True, blank=True)
    deal = models.ForeignKey("deals.Deal", on_delete=models.PROTECT, null=True, blank=True)
    handler = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="handled_complaints")
    route = models.CharField(max_length=20)
    status = models.CharField(max_length=24, default="RECEIVED", db_index=True)
    version = models.PositiveIntegerField(default=1)
    outcome = models.TextField(blank=True)
    reasons = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    acknowledgement_due_at = models.DateTimeField()
    resolution_due_at = models.DateTimeField(db_index=True)
    final_review_requested_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(status__in=["RECEIVED", "IN_REVIEW", "WAITING_INFORMATION", "RESOLVED", "UNDER_FINAL_REVIEW", "CLOSED"]), name="complaint_status_valid"), models.CheckConstraint(condition=models.Q(category__in=["FAKE_LISTING", "WRONG_LISTING", "CONDUCT", "PAYMENT", "PAYOUT", "PRIVACY", "VERIFICATION", "OTHER"]), name="complaint_type_valid")]


class ComplaintHistory(AppendOnly, TimeStampedModel):
    complaint = models.ForeignKey(Complaint, on_delete=models.PROTECT, related_name="history")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    status = models.CharField(max_length=24)
    reason = models.TextField()
    version = models.PositiveIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["complaint", "version"], name="complaint_history_version_unique")]


class ComplaintResponse(AppendOnly, TimeStampedModel):
    complaint = models.ForeignKey(Complaint, on_delete=models.PROTECT, related_name="responses")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    text = models.TextField()
    from_complainant = models.BooleanField(default=False)


class ComplaintEvidence(AppendOnly, TimeStampedModel):
    complaint = models.ForeignKey(Complaint, on_delete=models.PROTECT, related_name="evidence")
    media = models.OneToOneField("media.Media", on_delete=models.PROTECT)


class ComplaintNotice(TimeStampedModel):
    complaint = models.ForeignKey(Complaint, on_delete=models.PROTECT, related_name="notices")
    purpose = models.CharField(max_length=30)
    version = models.PositiveIntegerField()
    channels = models.JSONField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["complaint", "purpose", "version"], name="complaint_notice_unique")]
