from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import TimeStampedModel


class ListerIdentity(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        EXPIRED = "EXPIRED", "Expired"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="lister_identity",
    )
    national_id_number = models.CharField(max_length=100)
    national_id_photo_ref = models.CharField(max_length=500, blank=True)
    live_selfie_ref = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reviewed_lister_identities",
    )
    review_reason = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        super().clean()
        if self.reviewed_by_id and self.user_id and self.reviewed_by_id == self.user_id:
            raise ValidationError({"reviewed_by": "A lister cannot review their own identity."})

    def __str__(self):
        return f"ListerIdentity:{self.pk}"
