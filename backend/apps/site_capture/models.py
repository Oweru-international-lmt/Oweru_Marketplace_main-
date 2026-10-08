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
    verification_task = models.ForeignKey("verification.VerificationTask", null=True, blank=True, on_delete=models.PROTECT, related_name="site_captures", editable=False)
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
    measured_area_sqm = models.DecimalField(max_digits=22, decimal_places=2, null=True, blank=True, editable=False)
    area_difference_percent = models.DecimalField(max_digits=22, decimal_places=2, null=True, blank=True, editable=False)
    review_flags = models.JSONField(default=list, editable=False)
    overlap_findings = models.JSONField(default=list, editable=False)

    class Meta:
        ordering = ["-captured_at", "-created_at"]
        indexes = [
            models.Index(fields=["property", "status", "captured_at"], name="sitecap_prop_status_idx"),
        ]

    def __str__(self):
        return self.capture_id


class CaptureCorner(TimeStampedModel):
    capture = models.ForeignKey(SiteCapture, on_delete=models.PROTECT, related_name="corners")
    sequence = models.PositiveIntegerField()
    point = gis_models.PointField(srid=4326)
    accuracy_m = models.DecimalField(max_digits=12, decimal_places=2)
    observed_at = models.DateTimeField()
    device = models.CharField(max_length=255)

    class Meta:
        ordering = ["sequence"]
        constraints = [
            models.UniqueConstraint(fields=["capture", "sequence"], name="capture_corner_sequence_unique"),
            models.CheckConstraint(condition=models.Q(accuracy_m__gte=0), name="capture_corner_accuracy_nonnegative"),
        ]

    def save(self, *args, **kwargs):
        from rest_framework.exceptions import ValidationError
        if self.capture.status != SiteCapture.Status.DRAFT:
            raise ValidationError("Submitted corner evidence is locked.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        from rest_framework.exceptions import ValidationError
        if self.capture.status != SiteCapture.Status.DRAFT:
            raise ValidationError("Submitted corner evidence is locked.")
        return super().delete(*args, **kwargs)


class PublicMapLayer(TimeStampedModel):
    name = models.CharField(max_length=200)
    source_reference = models.CharField(max_length=1000)
    boundary = gis_models.MultiPolygonField(srid=4326)
    active = models.BooleanField(default=True)
    loaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)


class CaptureAsset(TimeStampedModel):
    capture = models.ForeignKey(SiteCapture, on_delete=models.PROTECT, related_name="assets")
    media = models.OneToOneField("media.Media", on_delete=models.PROTECT)
    source = models.CharField(max_length=10, choices=[("CAMERA", "Camera"), ("UPLOAD", "Gallery")])
    flags = models.JSONField(default=list)
    distance_m = models.DecimalField(max_digits=16, decimal_places=2, null=True)

    def save(self, *args, **kwargs):
        from rest_framework.exceptions import ValidationError
        if not self._state.adding:
            raise ValidationError("Capture provenance cannot be overwritten.")
        return super().save(*args, **kwargs)
