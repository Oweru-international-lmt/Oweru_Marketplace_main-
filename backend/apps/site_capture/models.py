from django.conf import settings
from django.contrib.gis.db import models as gis_models
from django.db import models

from apps.common.models import TimeStampedModel
from apps.properties.models import PropertyRecord


class SiteCapture(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted"

    capture_id = models.CharField(max_length=20, unique=True, editable=False, db_index=True)
    property = models.ForeignKey(PropertyRecord, on_delete=models.PROTECT, related_name="site_captures")
    captured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        editable=False,
        related_name="site_captures",
    )
    captured_at = models.DateTimeField(editable=False)
    observed_point = gis_models.PointField(srid=4326)
    observed_boundary = gis_models.PolygonField(srid=4326, null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)

    class Meta:
        ordering = ["-captured_at", "-created_at"]
        indexes = [
            models.Index(fields=["property", "status", "captured_at"], name="sitecap_prop_status_idx"),
        ]

    def __str__(self):
        return self.capture_id
