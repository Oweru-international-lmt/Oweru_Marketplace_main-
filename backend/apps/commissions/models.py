from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from apps.common.models import TimeStampedModel


class RateTable(TimeStampedModel):
    version = models.PositiveIntegerField(unique=True)
    total_rate = models.DecimalField(max_digits=7, decimal_places=6, default="0.10")
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(total_rate__gt=0, total_rate__lt=1), name="rate_total_valid")]

    def save(self, *args, **kwargs):
        if not self._state.adding and type(self).objects.filter(pk=self.pk, published_at__isnull=False).exists():
            raise ValidationError("Published rate versions are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Rate versions must remain preserved.")


class RateBand(TimeStampedModel):
    table = models.ForeignKey(RateTable, on_delete=models.PROTECT, related_name="bands")
    lower = models.DecimalField(max_digits=18, decimal_places=0)
    upper = models.DecimalField(max_digits=18, decimal_places=0, null=True, blank=True)
    oweru_rate = models.DecimalField(max_digits=7, decimal_places=6)
    agent_rate = models.DecimalField(max_digits=7, decimal_places=6)

    class Meta:
        ordering = ["lower"]
        constraints = [
            models.UniqueConstraint(fields=["table", "lower"], name="band_unique_lower"),
            models.CheckConstraint(condition=models.Q(lower__gte=0) & (models.Q(upper__isnull=True) | models.Q(upper__gte=models.F("lower"))), name="band_bounds_valid"),
            models.CheckConstraint(condition=models.Q(oweru_rate__gte=0, oweru_rate__lt=1, agent_rate__gte=0, agent_rate__lt=1), name="band_rates_valid"),
        ]

    def save(self, *args, **kwargs):
        if RateTable.objects.filter(pk=self.table_id, published_at__isnull=False).exists():
            raise ValidationError("Published rate bands are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.table.published_at:
            raise ValidationError("Published rate bands are immutable.")
        return super().delete(*args, **kwargs)
