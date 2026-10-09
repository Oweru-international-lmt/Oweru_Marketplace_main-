from django.conf import settings
from django.db import models
from apps.common.models import TimeStampedModel
from apps.verification.immutability import AppendOnly


class AdministrationHistory(AppendOnly, TimeStampedModel):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="administration_actions")
    entity_type = models.CharField(max_length=64)
    entity_id = models.UUIDField()
    reason = models.CharField(max_length=1000)
    before = models.JSONField()
    after = models.JSONField()
