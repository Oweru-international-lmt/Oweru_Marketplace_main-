from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import TimeStampedModel
from apps.lister_identity.evidence import normalize_evidence_reference
from apps.properties.models import PropertyRecord
from .immutability import AppendOnly


SAFE_SUBJECT_SNAPSHOT_FIELDS = frozenset({
    "property_id",
    "category",
    "title_type",
    "stated_size",
    "size_unit",
    "region_id",
    "district_id",
    "ward_id",
    "locality_id",
})


def _validate_subject_snapshot(value):
    if not isinstance(value, dict):
        raise ValidationError({"subject_snapshot": "Subject snapshot must be an object."})
    unsupported = set(value) - SAFE_SUBJECT_SNAPSHOT_FIELDS
    if unsupported:
        raise ValidationError({"subject_snapshot": "Subject snapshot contains unsupported fields."})
    return value


class PropertyVerification(TimeStampedModel):
    class Kind(models.TextChoices):
        DOCUMENT = "DOCUMENT", "Document"
        FIELD = "FIELD", "Field"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        EXPIRED = "EXPIRED", "Expired"
        REVOKED = "REVOKED", "Revoked"

    property = models.ForeignKey(PropertyRecord, on_delete=models.PROTECT, related_name="verifications")
    kind = models.CharField(max_length=16, choices=Kind.choices, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="property_verifications_submitted",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="property_verifications_reviewed",
    )
    submitted_at = models.DateTimeField()
    reviewed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=1000, null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    # This deliberately excludes exact geometry and private evidence references.
    subject_snapshot = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-submitted_at", "-created_at"]
        indexes = [
            models.Index(fields=["property", "kind", "status", "expires_at"], name="verification_effective_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(reviewed_by__isnull=True, reviewed_at__isnull=True)
                    | models.Q(reviewed_by__isnull=False, reviewed_at__isnull=False)
                ),
                name="verification_reviewer_pair",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(status="APPROVED")
                    | models.Q(reviewed_by__isnull=False, reviewed_at__isnull=False, expires_at__isnull=False)
                ),
                name="verification_approved_reviewed",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(status="REJECTED")
                    | models.Q(reviewed_by__isnull=False, reviewed_at__isnull=False)
                    & models.Q(rejection_reason__isnull=False)
                    & ~models.Q(rejection_reason="")
                ),
                name="verification_rejected_reason",
            ),
            models.CheckConstraint(
                condition=(models.Q(status="REVOKED", revoked_at__isnull=False) | ~models.Q(status="REVOKED")),
                name="verification_revoked_timestamp",
            ),
            models.UniqueConstraint(
                fields=["property", "kind"],
                condition=models.Q(kind="DOCUMENT", status__in=["PENDING", "APPROVED"]),
                name="verification_document_single_active",
            ),
            models.UniqueConstraint(
                fields=["property", "kind"],
                condition=models.Q(kind="FIELD", status__in=["PENDING", "APPROVED"]),
                name="verification_field_single_active",
            ),
        ]

    def clean(self):
        super().clean()
        self.subject_snapshot = _validate_subject_snapshot(self.subject_snapshot)
        if self.reviewed_by_id and self.submitted_by_id and self.reviewed_by_id == self.submitted_by_id:
            raise ValidationError({"reviewed_by": "A submitter cannot review their own property verification."})

    def save(self, *args, **kwargs):
        self.subject_snapshot = _validate_subject_snapshot(self.subject_snapshot)
        return super().save(*args, **kwargs)


class PropertyVerificationEvidence(AppendOnly, TimeStampedModel):
    class EvidenceType(models.TextChoices):
        TITLE_DOCUMENT = "TITLE_DOCUMENT", "Title document"
        FIELD_REPORT = "FIELD_REPORT", "Field report"
        OFFICIAL_ATTESTATION = "OFFICIAL_ATTESTATION", "Official attestation"

    verification = models.ForeignKey(PropertyVerification, on_delete=models.PROTECT, related_name="evidence")
    evidence_type = models.CharField(max_length=32, choices=EvidenceType.choices)
    evidence_ref = models.CharField(max_length=500)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="property_verification_evidence_created",
    )
    author_role = models.CharField(max_length=32, blank=True)
    device = models.CharField(max_length=255, blank=True)
    supersedes = models.OneToOneField("self", on_delete=models.PROTECT, null=True, blank=True, related_name="correction")

    class Meta:
        ordering = ["created_at", "id"]

    def clean(self):
        super().clean()
        self.evidence_ref = normalize_evidence_reference(self.evidence_ref, field_name="evidence_ref")

    def save(self, *args, **kwargs):
        self.evidence_ref = normalize_evidence_reference(self.evidence_ref, field_name="evidence_ref")
        return super().save(*args, **kwargs)


from .job_models import (  # noqa: E402,F401
    FullCheckProof, FullCheckReceipt, JobHistory, OwnerConsent, PropertyRelationship,
    TaskAssignment, TaskSubmission, VerificationJob, VerificationNotice,
    VerificationReport, VerificationResult, VerificationSetting, SettingHistory, VerificationTask, VerificationLevelSnapshot,
)
