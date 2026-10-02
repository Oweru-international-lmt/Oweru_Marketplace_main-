import uuid

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .managers import UserManager, normalize_email_address


class User(AbstractBaseUser, PermissionsMixin):
    class Language(models.TextChoices):
        ENGLISH = "en", "English"
        SWAHILI = "sw", "Kiswahili"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=30, unique=True)
    full_name = models.CharField(max_length=255)
    # Sign-in identifier. Stored lowercased so uniqueness and lookups ignore case.
    email = models.EmailField(unique=True)
    language = models.CharField(max_length=2, choices=Language.choices, default=Language.SWAHILI)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    account_category = models.CharField(max_length=12, choices=[("public", "Public"), ("operational", "Operational")], default="public", editable=False)
    failed_login_attempts = models.PositiveSmallIntegerField(default=0, editable=False)
    locked_until = models.DateTimeField(null=True, blank=True, editable=False)
    date_joined = models.DateTimeField(default=timezone.now, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["phone", "full_name"]

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(account_category__in=["public", "operational"]), name="user_category_valid"),
            models.CheckConstraint(condition=~Q(phone=""), name="user_phone_not_blank"),
            models.CheckConstraint(condition=~Q(email=""), name="user_email_not_blank"),
            models.CheckConstraint(condition=Q(language__in=["en", "sw"]), name="user_language_supported"),
            models.CheckConstraint(condition=Q(failed_login_attempts__lte=5), name="login_failures_max_five"),
        ]

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        self.email = normalize_email_address(self.email)
        return super().save(*args, **kwargs)

    def _effective_roles(self):
        from authorization.catalog import OPERATIONAL_ROLES, PUBLIC_ROLES

        return self.user_roles.filter(is_active=True, role__is_active=True, user__is_active=True).filter(
            Q(user__account_category="public", role__code__in=PUBLIC_ROLES)
            | Q(user__account_category="operational", role__code__in=OPERATIONAL_ROLES)
        )

    def has_role(self, code):
        return self.is_active and self._effective_roles().filter(role__code=code).exists()

    def has_marketplace_permission(self, code):
        return self.is_active and self._effective_roles().filter(
            role__role_permissions__permission__code=code,
        ).exists()


class SensitiveConfirmation(models.Model):
    """Single-use, purpose-bound confirmation token metadata."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sensitive_confirmations")
    purpose = models.CharField(max_length=64)
    subject_type = models.CharField(max_length=100, blank=True)
    subject_id = models.CharField(max_length=100, blank=True)
    token_digest = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=("user", "purpose", "expires_at"), name="confirm_user_purp_idx"),
            models.Index(fields=("subject_type", "subject_id"), name="confirm_subject_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            persisted = type(self).objects.get(pk=self.pk)
            allowed = (
                persisted.consumed_at is None
                and self.consumed_at is not None
                and persisted.user_id == self.user_id
                and persisted.purpose == self.purpose
                and persisted.subject_type == self.subject_type
                and persisted.subject_id == self.subject_id
                and persisted.token_digest == self.token_digest
                and persisted.expires_at == self.expires_at
            )
            if not allowed:
                raise ValueError("Sensitive confirmation records are immutable except for one-time consumption.")
        return super().save(*args, **kwargs)
