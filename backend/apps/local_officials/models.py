import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from apps.common.models import TimeStampedModel
from apps.localities.models import District, Region, Ward, Locality


OFFICIAL_ID_PREFIX = "OFF"
ASSIGNMENT_ID_PREFIX = "JUR"
IDENTIFIER_TOKEN_BYTES = 8
IDENTIFIER_MAX_ATTEMPTS = 8


def _identifier(prefix):
    return f"{prefix}-{secrets.token_hex(IDENTIFIER_TOKEN_BYTES).upper()}"


def generate_official_id():
    for _ in range(IDENTIFIER_MAX_ATTEMPTS):
        candidate = _identifier(OFFICIAL_ID_PREFIX)
        if not LocalOfficialProfile.objects.filter(official_id=candidate).exists():
            return candidate
    raise ValidationError({"official_id": "Could not generate a unique official identifier."})


def generate_assignment_id():
    for _ in range(IDENTIFIER_MAX_ATTEMPTS):
        candidate = _identifier(ASSIGNMENT_ID_PREFIX)
        if not OfficialJurisdictionAssignment.objects.filter(assignment_id=candidate).exists():
            return candidate
    raise ValidationError({"assignment_id": "Could not generate a unique jurisdiction identifier."})


class LocalOfficialProfile(TimeStampedModel):
    official_id = models.CharField(max_length=20, unique=True, editable=False, db_index=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="local_official_profile",
    )
    official_number = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["official_id"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(official_number=""),
                name="local_official_number_not_blank",
            ),
        ]

    def clean(self):
        super().clean()
        self.official_number = (self.official_number or "").strip()
        if not self.official_number:
            raise ValidationError({"official_number": "Official number is required."})

    def save(self, *args, **kwargs):
        self.official_number = (self.official_number or "").strip()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.official_id


class OfficialJurisdictionAssignment(TimeStampedModel):
    class ScopeType(models.TextChoices):
        REGION = "REGION", "Region"
        DISTRICT = "DISTRICT", "District"
        WARD = "WARD", "Ward"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        REVOKED = "REVOKED", "Revoked"

    assignment_id = models.CharField(max_length=20, unique=True, editable=False, db_index=True)
    official = models.ForeignKey(
        LocalOfficialProfile,
        on_delete=models.PROTECT,
        related_name="jurisdiction_assignments",
    )
    scope_type = models.CharField(max_length=16, choices=ScopeType.choices)
    region = models.ForeignKey(Region, on_delete=models.PROTECT, null=True, blank=True, related_name="official_assignments")
    district = models.ForeignKey(District, on_delete=models.PROTECT, null=True, blank=True, related_name="official_assignments")
    ward = models.ForeignKey(Ward, on_delete=models.PROTECT, null=True, blank=True, related_name="official_assignments")
    starts_at = models.DateTimeField(db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="official_jurisdictions_assigned",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="official_jurisdictions_revoked",
    )

    class Meta:
        ordering = ["-starts_at", "-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(scope_type="REGION", region__isnull=False, district__isnull=True, ward__isnull=True)
                    | Q(scope_type="DISTRICT", region__isnull=True, district__isnull=False, ward__isnull=True)
                    | Q(scope_type="WARD", region__isnull=True, district__isnull=True, ward__isnull=False)
                ),
                name="official_scope_exact_area",
            ),
            models.CheckConstraint(
                condition=Q(expires_at__isnull=True) | Q(expires_at__gt=F("starts_at")),
                name="official_scope_valid_period",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status="ACTIVE", revoked_at__isnull=True, revoked_by__isnull=True)
                    | Q(status="REVOKED", revoked_at__isnull=False, revoked_by__isnull=False)
                ),
                name="official_scope_revocation_pair",
            ),
            models.UniqueConstraint(
                fields=["official", "region"],
                condition=Q(status="ACTIVE", scope_type="REGION"),
                name="official_active_region_unique",
            ),
            models.UniqueConstraint(
                fields=["official", "district"],
                condition=Q(status="ACTIVE", scope_type="DISTRICT"),
                name="official_active_district_unique",
            ),
            models.UniqueConstraint(
                fields=["official", "ward"],
                condition=Q(status="ACTIVE", scope_type="WARD"),
                name="official_active_ward_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["official", "status", "starts_at"], name="official_scope_effective_idx"),
        ]

    def clean(self):
        super().clean()
        areas = {
            self.ScopeType.REGION: self.region_id,
            self.ScopeType.DISTRICT: self.district_id,
            self.ScopeType.WARD: self.ward_id,
        }
        expected_area = areas.get(self.scope_type)
        supplied_area_count = sum(area is not None for area in areas.values())
        errors = {}
        if expected_area is None or supplied_area_count != 1:
            errors["scope_type"] = "Scope type must match exactly one administrative area."
        if self.expires_at is not None and self.starts_at is not None and self.expires_at <= self.starts_at:
            errors["expires_at"] = "Expiry must be later than the assignment start."
        if self.status == self.Status.ACTIVE:
            if self.revoked_at is not None or self.revoked_by_id is not None:
                errors["status"] = "Active assignments cannot have revocation metadata."
        elif self.status == self.Status.REVOKED:
            if self.revoked_at is None or self.revoked_by_id is None:
                errors["status"] = "Revoked assignments require revocation metadata."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.assignment_id


class OfficialLocalityCoverage(TimeStampedModel):
    official = models.ForeignKey(LocalOfficialProfile, on_delete=models.PROTECT, related_name="locality_coverage")
    locality = models.ForeignKey(Locality, on_delete=models.PROTECT, related_name="official_coverage")
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    starts_at = models.DateTimeField()
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["official", "locality"], condition=Q(revoked_at__isnull=True), name="official_exact_locality_active"),
            models.CheckConstraint(condition=Q(expires_at__isnull=True) | Q(expires_at__gt=F("starts_at")), name="official_locality_valid_period"),
        ]
        indexes = [models.Index(fields=["locality", "revoked_at"], name="official_exact_locality_idx")]
