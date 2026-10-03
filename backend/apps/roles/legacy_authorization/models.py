from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.common.models import TimeStampedModel


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
    code = models.CharField(max_length=30, choices=RoleCode.choices, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        constraints = [models.CheckConstraint(condition=Q(code__in=[choice.value for choice in RoleCode]), name="role_code_valid")]

    def __str__(self):
        return self.name


class Permission(TimeStampedModel):
    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code


class RolePermission(TimeStampedModel):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_permissions")
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name="role_permissions")

    class Meta:
        constraints = [models.UniqueConstraint(fields=("role", "permission"), name="uniq_role_permission")]


class UserRole(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="user_roles")
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="user_roles")
    is_active = models.BooleanField(default=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="role_assignments_made",
    )

    class Meta:
        constraints = [models.UniqueConstraint(fields=("user", "role"), name="uniq_user_role")]
        indexes = [models.Index(fields=("user", "is_active"), name="userrole_active_idx")]

    def __str__(self):
        return f"{self.user} – {self.role.code}"
