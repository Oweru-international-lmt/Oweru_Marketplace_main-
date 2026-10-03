from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.common.models import TimeStampedModel, UUIDModel


class RoleCode(models.TextChoices):
    BUYER = "buyer", "Buyer"
    OWNER = "owner", "Owner"
    AGENT = "agent", "Agent"
    LOCAL_OFFICIAL = "local_official", "Local official"
    PROFESSIONAL = "professional", "Professional"
    VERIFIER = "verifier", "Verifier"
    MARKETER = "marketer", "Marketer"
    MANAGEMENT = "management", "Management"


class Role(TimeStampedModel):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.name


class UserRole(UUIDModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="m01_roles")
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="user_assignments")
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="m01_role_assignments_made",
    )
    assigned_at = models.DateTimeField(default=timezone.now, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-assigned_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role"],
                condition=Q(is_active=True),
                name="uniq_active_m01_user_role",
            )
        ]
        indexes = [
            models.Index(fields=["user", "is_active"], name="m01_userrole_active_idx"),
            models.Index(fields=["role", "is_active"], name="m01_role_active_idx"),
        ]

    def __str__(self):
        return f"{self.user_id}:{self.role.code}"
