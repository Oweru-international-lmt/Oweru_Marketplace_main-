from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel


class AppendOnlyQuerySet(models.QuerySet):
    def bulk_update(self, objs, fields, batch_size=None):
        raise RuntimeError("Audit events cannot be updated.")

    def update(self, **kwargs):
        raise RuntimeError("Audit events cannot be updated.")

    def update_or_create(self, *args, **kwargs):
        raise RuntimeError("Audit events cannot be updated or upserted.")

    def delete(self):
        raise RuntimeError("Audit events cannot be deleted.")


class AuditEvent(TimeStampedModel):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="audit_events")
    action = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=100, blank=True)
    before_state = models.JSONField(default=dict, blank=True)
    after_state = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=("entity_type", "entity_id"), name="audit_entity_idx"),
            models.Index(fields=("actor", "created_at"), name="audit_actor_time_idx"),
            models.Index(fields=("action", "created_at"), name="audit_action_time_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("Audit events cannot be modified.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Audit events cannot be deleted.")

    def __str__(self):
        return f"{self.action} on {self.entity_type}:{self.entity_id}"
