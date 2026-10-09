import secrets
from django.conf import settings
from django.db import models
from apps.common.models import TimeStampedModel
from apps.verification.immutability import AppendOnly


def reference():
    return "FRC-" + secrets.token_hex(8).upper()


class FreeCheck(AppendOnly, TimeStampedModel):
    reference = models.CharField(max_length=30, unique=True, default=reference)
    property = models.OneToOneField("properties.PropertyRecord", on_delete=models.PROTECT)
    phone = models.CharField(max_length=30, db_index=True)
    email = models.EmailField(blank=True)
    language = models.CharField(max_length=2, default="sw")
    description = models.CharField(max_length=4000)
    external_url = models.URLField(max_length=1000, blank=True)
    verdicts = models.JSONField()
    expires_at = models.DateTimeField()
    request_key = models.CharField(max_length=128)
    input_digest = models.CharField(max_length=64)
    token_digest = models.CharField(max_length=64)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["phone", "request_key"], name="free_check_request_unique"), models.CheckConstraint(condition=models.Q(language__in=["sw", "en"]), name="free_check_language_valid")]


class FreeCheckReport(AppendOnly, TimeStampedModel):
    free_check = models.ForeignKey(FreeCheck, on_delete=models.PROTECT, related_name="reports")
    media = models.OneToOneField("media.Media", on_delete=models.PROTECT)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["free_check", "version"], name="free_report_version_unique")]


class FreeCheckPhoto(AppendOnly, TimeStampedModel):
    free_check = models.ForeignKey(FreeCheck, on_delete=models.PROTECT, related_name="photos")
    media = models.OneToOneField("media.Media", on_delete=models.PROTECT)


class FreeCheckLead(AppendOnly, TimeStampedModel):
    """Outside-property prospect; existing sales Leads remain listing-bound."""
    free_check = models.OneToOneField(FreeCheck, on_delete=models.PROTECT, related_name="prospect")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)

