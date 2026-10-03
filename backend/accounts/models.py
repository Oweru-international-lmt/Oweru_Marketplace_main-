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
    # ACC-05 / ACC-01: set when the person opens a confirmation link; cleared if the value changes.
    email_verified_at = models.DateTimeField(null=True, blank=True, editable=False)
    phone_verified_at = models.DateTimeField(null=True, blank=True, editable=False)
    # ACC-06: staff and partner accounts start with a temporary password.
    must_change_password = models.BooleanField(default=False)
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

    def effective_role_codes(self):
        """Role codes that currently grant access, using the same rules as has_role."""
        if not self.is_active:
            return set()
        return set(self._effective_roles().values_list("role__code", flat=True))

    def effective_permission_codes(self):
        """Permission codes that currently grant access, using the same rules as has_marketplace_permission."""
        if not self.is_active:
            return set()
        codes = self._effective_roles().values_list("role__role_permissions__permission__code", flat=True)
        return {code for code in codes if code}


class SensitiveConfirmation(models.Model):
    """Single-use, purpose-bound confirmation token metadata.

    SRD 20.3: a link works once; the decision, time, recipient, IP address and
    browser are stored when it is used.
    """

    class Decision(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmed"
        DECLINED = "declined", "Declined"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sensitive_confirmations")
    purpose = models.CharField(max_length=64)
    subject_type = models.CharField(max_length=100, blank=True)
    subject_id = models.CharField(max_length=100, blank=True)
    # Where the link was sent (phone number or email address).
    recipient = models.CharField(max_length=255, blank=True)
    token_digest = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    decision = models.CharField(max_length=16, choices=Decision.choices, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=("user", "purpose", "expires_at"), name="confirm_user_purp_idx"),
            models.Index(fields=("subject_type", "subject_id"), name="confirm_subject_idx"),
        ]

    _IDENTITY_FIELDS = ("user_id", "purpose", "subject_type", "subject_id", "recipient", "token_digest", "expires_at")

    def save(self, *args, **kwargs):
        if not self._state.adding:
            persisted = type(self).objects.get(pk=self.pk)
            # Only the one-time consumption (with its decision record) may change a stored row.
            allowed = (
                persisted.consumed_at is None
                and self.consumed_at is not None
                and all(getattr(persisted, field) == getattr(self, field) for field in self._IDENTITY_FIELDS)
            )
            if not allowed:
                raise ValueError("Sensitive confirmation records are immutable except for one-time consumption.")
        return super().save(*args, **kwargs)


class AccountDeletionRequest(models.Model):
    """ACC-08: a user asks for deletion; Management decides, keeping records the law requires."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        DECLINED = "declined", "Declined"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="deletion_requests")
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    requested_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True, related_name="deletion_requests_resolved"
    )
    resolution_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-requested_at"]
        constraints = [
            models.UniqueConstraint(
                fields=("user",), condition=Q(status="pending"), name="one_pending_deletion_request_per_user"
            ),
        ]
