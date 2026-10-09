import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.common.models import TimeStampedModel
from .immutability import AppendOnly


class VerificationSetting(TimeStampedModel):
    key = models.CharField(max_length=64, unique=True)
    value = models.JSONField()
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    version = models.PositiveIntegerField(default=0)


class SettingHistory(AppendOnly, TimeStampedModel):
    setting = models.ForeignKey(VerificationSetting, on_delete=models.PROTECT, related_name="history")
    version = models.PositiveIntegerField()
    value = models.JSONField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["setting", "version"], name="setting_history_version_unique")]


class PropertyRelationship(AppendOnly, TimeStampedModel):
    property = models.ForeignKey("properties.PropertyRecord", on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.CharField(max_length=1000)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["property", "user"], name="verification_relationship_unique")]


class VerificationLevelSnapshot(TimeStampedModel):
    listing = models.OneToOneField("listings.Listing", on_delete=models.PROTECT, related_name="verification_snapshot")
    level = models.PositiveSmallIntegerField(default=0, editable=False)
    calculated_at = models.DateTimeField()

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(level__gte=0, level__lte=3), name="stored_verification_level_valid")]


class VerificationJob(TimeStampedModel):
    class Status(models.TextChoices):
        AWAITING_PAYMENT = "AWAITING_PAYMENT", "Awaiting payment"
        AWAITING_CONSENT = "AWAITING_CONSENT", "Awaiting consent"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        UNDER_REVIEW = "UNDER_REVIEW", "Under review"
        PASSED = "PASSED", "Passed"
        PROBLEM_FOUND = "PROBLEM_FOUND", "Problem found"
        NOT_COMPLETED = "NOT_COMPLETED", "Not completed"

    property = models.ForeignKey("properties.PropertyRecord", on_delete=models.PROTECT, related_name="verification_jobs")
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="full_checks")
    listing = models.ForeignKey("listings.Listing", null=True, blank=True, on_delete=models.PROTECT)
    kind = models.CharField(max_length=16, choices=[("FULL", "Full check"), ("OUTSIDE_FULL", "Outside full check")])
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.AWAITING_PAYMENT, db_index=True)
    verifier = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="assigned_full_checks")
    fee = models.DecimalField(max_digits=18, decimal_places=0)
    scope_snapshot = models.JSONField()
    subject_snapshot = models.JSONField()
    payment_reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    consent_due_at = models.DateTimeField(null=True, blank=True)
    contact_due_at = models.DateTimeField(null=True, blank=True)
    owner_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="consent_full_checks")
    owner_name = models.CharField(max_length=255, blank=True)
    owner_phone = models.CharField(max_length=30, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    refresh_limit_at = models.DateTimeField(null=True, blank=True)
    invalidated_at = models.DateTimeField(null=True, blank=True)
    invalidation_reason = models.CharField(max_length=1000, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(fee__gt=0), name="full_check_fee_positive"),
            models.CheckConstraint(condition=Q(kind__in=["FULL", "OUTSIDE_FULL"]), name="full_check_kind_valid"),
            models.CheckConstraint(condition=Q(status__in=["AWAITING_PAYMENT", "AWAITING_CONSENT", "IN_PROGRESS", "UNDER_REVIEW", "PASSED", "PROBLEM_FOUND", "NOT_COMPLETED"]), name="full_check_status_valid"),
            models.CheckConstraint(condition=~Q(status="PASSED") | Q(completed_at__isnull=False, expires_at__isnull=False, verifier__isnull=False), name="full_check_passed_dates"),
            models.CheckConstraint(condition=Q(expires_at__isnull=True) | Q(expires_at__gt=F("completed_at")), name="full_check_valid_expiry"),
            models.UniqueConstraint(fields=["buyer", "property"], condition=Q(status__in=["AWAITING_PAYMENT", "AWAITING_CONSENT", "IN_PROGRESS", "UNDER_REVIEW"]), name="one_open_buyer_property_check"),
        ]
        indexes = [models.Index(fields=["property", "status", "expires_at"], name="full_check_effective_idx")]


class VerificationTask(TimeStampedModel):
    class Kind(models.TextChoices):
        SITE_CAPTURE = "SITE_CAPTURE", "Site capture"
        LOCAL_OFFICE = "LOCAL_OFFICE", "Local office"
        PROFESSIONAL = "PROFESSIONAL", "Professional"
        REGISTRY = "REGISTRY", "Land Registry"

    job = models.ForeignKey(VerificationJob, on_delete=models.PROTECT, related_name="tasks")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    status = models.CharField(max_length=20, default="UNASSIGNED", choices=[(v, v) for v in ["UNASSIGNED", "NEEDS_OFFICIAL", "ASSIGNED", "ACCEPTED", "SUBMITTED", "TIMED_OUT"]], db_index=True)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="verification_tasks")
    professional_type = models.CharField(max_length=24, blank=True)
    due_at = models.DateTimeField(null=True, blank=True, db_index=True)
    required = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["job", "kind"], condition=~Q(kind="PROFESSIONAL"), name="one_core_task_per_job"),
            models.CheckConstraint(condition=Q(kind__in=["SITE_CAPTURE", "LOCAL_OFFICE", "PROFESSIONAL", "REGISTRY"]), name="verification_task_kind_valid"),
            models.CheckConstraint(condition=Q(kind="PROFESSIONAL", professional_type__in=["AFISA_MIPANGO_MIJI", "PLANNER", "SURVEYOR"]) | (~Q(kind="PROFESSIONAL") & Q(professional_type="")), name="verification_task_prof_type_valid"),
            models.UniqueConstraint(fields=["job", "professional_type"], condition=Q(kind="PROFESSIONAL"), name="one_professional_type_per_job"),
            models.CheckConstraint(condition=Q(status__in=["UNASSIGNED", "NEEDS_OFFICIAL", "ASSIGNED", "ACCEPTED", "SUBMITTED", "TIMED_OUT"]), name="verification_task_status_valid"),
            models.CheckConstraint(condition=~Q(status__in=["ASSIGNED", "ACCEPTED"]) | Q(assignee__isnull=False), name="verification_task_assigned_user"),
        ]


class TaskAssignment(AppendOnly, TimeStampedModel):
    task = models.ForeignKey(VerificationTask, on_delete=models.PROTECT, related_name="assignment_history")
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="verification_assignments_made")
    action = models.CharField(max_length=16)
    reason = models.CharField(max_length=1000, blank=True)


class TaskSubmission(AppendOnly, TimeStampedModel):
    task = models.ForeignKey(VerificationTask, on_delete=models.PROTECT, related_name="submissions")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    author_role = models.CharField(max_length=32)
    author_name = models.CharField(max_length=255)
    registration_number = models.CharField(max_length=100, blank=True)
    device = models.CharField(max_length=255)
    findings = models.JSONField()
    signed_and_stamped = models.BooleanField(default=False)
    report = models.ForeignKey("media.Media", null=True, blank=True, on_delete=models.PROTECT)
    capture = models.ForeignKey("site_capture.SiteCapture", null=True, blank=True, on_delete=models.PROTECT)
    version = models.PositiveIntegerField(default=1)
    supersedes = models.OneToOneField("self", null=True, blank=True, on_delete=models.PROTECT, related_name="correction")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["task", "version"], name="task_submission_version_unique"), models.CheckConstraint(condition=Q(version__gte=1), name="task_submission_version_positive")]


class JobHistory(AppendOnly, TimeStampedModel):
    job = models.ForeignKey(VerificationJob, on_delete=models.PROTECT, related_name="history")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    status = models.CharField(max_length=24)
    reason = models.CharField(max_length=1000, blank=True)


class FullCheckProof(AppendOnly, TimeStampedModel):
    job = models.ForeignKey(VerificationJob, on_delete=models.PROTECT, related_name="payment_proofs")
    media = models.ForeignKey("media.Media", on_delete=models.PROTECT)
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    digest = models.CharField(max_length=64)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["job", "digest"], name="full_check_proof_content_unique")]


class FullCheckReceipt(AppendOnly, TimeStampedModel):
    job = models.OneToOneField(VerificationJob, on_delete=models.PROTECT, related_name="payment_receipt")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=18, decimal_places=0)
    bank_reference = models.CharField(max_length=255)
    tax_receipt_number = models.CharField(max_length=255, unique=True)
    tax_receipt = models.ForeignKey("media.Media", on_delete=models.PROTECT)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name="full_check_receipt_positive")]


class OwnerConsent(AppendOnly, TimeStampedModel):
    job = models.OneToOneField(VerificationJob, on_delete=models.PROTECT, related_name="consent")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    delivery = models.OneToOneField("payments.ConfirmationDelivery", null=True, blank=True, on_delete=models.PROTECT)
    decision = models.CharField(max_length=8, choices=[("CONFIRM", "Confirm"), ("DECLINE", "Decline")])
    recipient_phone = models.CharField(max_length=30)
    context = models.JSONField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device = models.CharField(max_length=2000, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(decision__in=["CONFIRM", "DECLINE"]), name="full_check_consent_decision_valid"),
            models.CheckConstraint(condition=Q(actor__isnull=False, delivery__isnull=True) | Q(actor__isnull=True, delivery__isnull=False), name="full_check_consent_authority"),
            models.CheckConstraint(condition=~Q(recipient_phone=""), name="full_check_consent_phone_required"),
        ]


class VerificationResult(AppendOnly, TimeStampedModel):
    job = models.OneToOneField(VerificationJob, on_delete=models.PROTECT, related_name="result")
    verifier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    result = models.CharField(max_length=20, choices=[("PASSED", "Passed"), ("PROBLEM_FOUND", "Problem found"), ("NOT_COMPLETED", "Not completed")])
    risk_assessment = models.TextField()
    not_checked = models.JSONField(default=list)
    evidence_basis = models.JSONField()

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(result__in=["PASSED", "PROBLEM_FOUND", "NOT_COMPLETED"]), name="full_check_result_valid")]


class VerificationReport(AppendOnly, TimeStampedModel):
    job = models.ForeignKey(VerificationJob, on_delete=models.PROTECT, related_name="reports")
    result = models.ForeignKey(VerificationResult, on_delete=models.PROTECT)
    media = models.ForeignKey("media.Media", on_delete=models.PROTECT)
    language = models.CharField(max_length=2)
    version = models.PositiveIntegerField(default=1)
    assessment_snapshot = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["job", "version"], name="full_check_report_version_unique"), models.CheckConstraint(condition=Q(version__gte=1, language__in=["sw", "en"]), name="full_check_report_version_language")]


class VerificationNotice(TimeStampedModel):
    job = models.ForeignKey(VerificationJob, null=True, blank=True, on_delete=models.PROTECT)
    task = models.ForeignKey(VerificationTask, null=True, blank=True, on_delete=models.PROTECT)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    phone = models.CharField(max_length=30, blank=True)
    purpose = models.CharField(max_length=40)
    channels = models.JSONField(default=list)
    sent_at = models.DateTimeField(null=True, blank=True)
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="verification_notices_sent")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["job", "task", "recipient", "phone", "purpose"], nulls_distinct=False, name="verification_notice_unique")]
