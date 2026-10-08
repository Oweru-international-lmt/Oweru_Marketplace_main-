from contextlib import contextmanager
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from apps.audit.services import create_audit_log
from apps.leads.policies import authorize
from apps.payments.documents import pending_objects, save_document, validate_document
from apps.properties.models import PropertyRecord
from .models import VerificationJob, VerificationTask, TaskSubmission, JobHistory, VerificationNotice
from .conflicts import has_property_conflict


def lock_job(job_id):
    # Global order: PropertyRecord -> VerificationJob -> VerificationTask.
    try:
        prop_id = VerificationJob.objects.values_list("property_id", flat=True).get(pk=job_id)
        PropertyRecord.objects.select_for_update().get(pk=prop_id)
        return VerificationJob.objects.select_for_update(of=("self",)).select_related("property", "listing", "buyer", "verifier").get(pk=job_id)
    except VerificationJob.DoesNotExist as exc:
        raise NotFound("Full Check not found.") from exc


def lock_task(task_id):
    try:
        job_id = VerificationTask.objects.values_list("job_id", flat=True).get(pk=task_id)
    except VerificationTask.DoesNotExist as exc:
        raise NotFound("Verification task not found.") from exc
    job = lock_job(job_id)
    task = VerificationTask.objects.select_for_update().get(pk=task_id)
    task.job = job
    return job, task


def require_responsible_verifier(actor, job, permission="verification.record_result"):
    actor = authorize(actor, permission)
    if not actor.has_role("verifier") or job.verifier_id != actor.pk or has_property_conflict(actor, job.property):
        raise PermissionDenied("The nonconflicted responsible Verifier is required.")
    return actor


def require_work(job):
    if job.status != "IN_PROGRESS" or job.invalidated_at or not hasattr(job, "payment_receipt") or not hasattr(job, "consent") or job.consent.decision != "CONFIRM":
        raise ValidationError("Confirmed payment and owner consent are required before verification work.")


@contextmanager
def private_write_scope():
    objects = []
    parent = pending_objects.get()
    token = pending_objects.set(objects)
    try:
        yield
        if parent is not None:
            parent.extend(objects)
    except Exception:
        for storage, key in objects:
            storage.delete_private_object(key=key)
        raise
    finally:
        pending_objects.reset(token)


def require_task_actor(actor, job, task):
    if task.kind == "SITE_CAPTURE":
        actor = authorize(actor, "listing.update")
        if actor is None or task.assignee_id != actor.pk:
            raise PermissionDenied("Only the assigned owner or agent may submit site capture.")
        if job.listing_id and job.listing.lister_id != actor.pk or not job.listing_id and job.owner_user_id != actor.pk:
            raise PermissionDenied("Current property owner/lister assignment is required.")
        return actor
    actor = authorize(actor, "verification.complete_task")
    if has_property_conflict(actor, job.property):
        raise PermissionDenied("Conflicted people cannot verify this property.")
    if task.kind == "LOCAL_OFFICE":
        from apps.local_officials.full_check import can_submit_official
        if not can_submit_official(actor, task):
            raise PermissionDenied("Current exact-locality authority is required.")
    elif task.kind == "PROFESSIONAL":
        from apps.professionals.services import effective_profile, eligible_professionals
        profile = effective_profile(actor)
        if profile is None or task.assignee_id != actor.pk or task.status != "ACCEPTED" or profile.pk not in {p.pk for p in eligible_professionals(property_record=job.property, professional_type=task.professional_type)}:
            raise PermissionDenied("An eligible accepted professional assignment is required.")
    elif task.kind == "REGISTRY":
        require_responsible_verifier(actor, job, "verification.complete_task")
    else:
        raise ValidationError("Unsupported task kind.")
    return actor


def validate_findings(task, findings, capture):
    if task.kind == "LOCAL_OFFICE":
        from apps.local_officials.full_check import validate_answers
        return validate_answers(findings)
    fields = {
        "AFISA_MIPANGO_MIJI": {"permitted_use", "planned_roads_or_reserves", "supporting_extracts"},
        "PLANNER": {"layout", "development_restrictions", "planning_context"},
        "SURVEYOR": {"beacon_photos", "overlap_notes"},
        "REGISTRY": {"search_result", "reference"},
        "SITE_CAPTURE": set(),
    }
    expected = fields[task.professional_type if task.kind == "PROFESSIONAL" else task.kind]
    if not isinstance(findings, dict) or set(findings) != expected:
        raise ValidationError({"findings": f"Required fields: {', '.join(sorted(expected)) or 'empty object'}."})
    if any(not isinstance(value, str) or not value.strip() or len(value) > 4000 for value in findings.values()):
        raise ValidationError("Findings must contain nonempty bounded text.")
    if task.kind == "SITE_CAPTURE" or task.professional_type == "SURVEYOR":
        from apps.site_capture.services import require_full_check_capture
        if capture is None:
            raise ValidationError("Submitted site capture is required.")
        require_full_check_capture(capture, task.job.property)
        findings = {**findings, "measured_area_sqm": str(capture.measured_area_sqm), "review_flags": capture.review_flags}
    return findings


def transition(job, status, actor, reason="", request=None):
    before = job.status
    job.status = status
    job.save()
    JobHistory.objects.create(job=job, status=status, actor=actor, reason=reason)
    create_audit_log(actor=actor, action="full_check.transitioned", entity_type="VerificationJob", entity_id=job.pk, before={"status": before}, after={"status": status}, request=request)


def submit_task(*, actor, task_id, findings, device, report=None, capture=None, signed_and_stamped=False, request=None):
    # Cleanup surrounds commit as well as audit errors.
    with private_write_scope(), transaction.atomic():
        job, task = lock_task(task_id)
        require_work(job)
        actor = require_task_actor(actor, job, task)
        if task.status not in {"ASSIGNED", "ACCEPTED"} or task.due_at and task.due_at <= timezone.now():
            raise ValidationError("Only a live assigned task may be submitted.")
        if not isinstance(device, str) or not device.strip() or len(device) > 255:
            raise ValidationError("Submission device is required.")
        normalized = validate_findings(task, findings, capture)
        if capture is not None and (task.kind == "SITE_CAPTURE" or task.professional_type == "SURVEYOR") and capture.captured_by_id != actor.pk:
            raise PermissionDenied("Site evidence must have been captured by the assigned submitting person.")
        if capture is not None and capture.verification_task_id and capture.verification_task_id != task.pk:
            raise PermissionDenied("Capture evidence belongs to another Full Check task.")
        if task.kind == "LOCAL_OFFICE" and signed_and_stamped is not True:
            raise ValidationError("The official must attest that the uploaded confirmation is signed and stamped.")
        if task.kind != "SITE_CAPTURE" and report is None:
            raise ValidationError("A private report or signed/stamped confirmation is required.")
        if task.kind == "PROFESSIONAL" and task.professional_type == "SURVEYOR":
            from apps.media.models import Media
            from django.contrib.contenttypes.models import ContentType
            if not Media.objects.filter(content_type=ContentType.objects.get_for_model(capture), object_id=capture.pk, mime_type__startswith="image/").exists():
                raise ValidationError("Surveyor capture requires beacon photos.")
        media = save_document(actor=actor, owner=task, upload=report) if report else None
        profile = getattr(actor, "professional_profile", None) if task.kind == "PROFESSIONAL" else getattr(actor, "local_official_profile", None) if task.kind == "LOCAL_OFFICE" else None
        previous = task.submissions.order_by("-version").first()
        submission = TaskSubmission.objects.create(task=task, author=actor, author_role={"LOCAL_OFFICE": "local_official", "PROFESSIONAL": "professional", "REGISTRY": "verifier", "SITE_CAPTURE": "lister"}[task.kind], author_name=actor.full_name, registration_number=(getattr(profile, "registration_number", "") or getattr(profile, "official_number", "")), device=device.strip(), findings=normalized, signed_and_stamped=signed_and_stamped, report=media, capture=capture, version=previous.version + 1 if previous else 1, supersedes=previous)
        task.status = "SUBMITTED"
        task.save()
        if task.kind == "SITE_CAPTURE" or task.kind == "PROFESSIONAL" and task.professional_type == "SURVEYOR":
            from apps.local_officials.full_check import route_task
            for local in job.tasks.select_for_update().filter(kind="LOCAL_OFFICE", status="UNASSIGNED"):
                route_task(local, job.verifier)
        create_audit_log(actor=actor, action="verification.task_submitted", entity_type="VerificationTask", entity_id=task.pk, before={}, after={"submission_id": str(submission.pk), "version": submission.version, "kind": task.kind}, request=request)
        if not job.tasks.filter(required=True).exclude(status="SUBMITTED").exists():
            transition(job, "UNDER_REVIEW", actor, request=request)
        return submission


@transaction.atomic
def reopen_task(*, actor, task_id, reason, request=None):
    job, task = lock_task(task_id)
    actor = require_responsible_verifier(actor, job)
    if job.status not in {"IN_PROGRESS", "UNDER_REVIEW"} or task.status != "SUBMITTED" or not reason.strip():
        raise ValidationError("Only submitted work in an unfinished job may receive a correction request.")
    task.status = "ACCEPTED" if task.kind == "PROFESSIONAL" else "ASSIGNED"
    task.save()
    transition(job, "IN_PROGRESS", actor, reason.strip(), request)
    create_audit_log(actor=actor, action="verification.correction_requested", entity_type="VerificationTask", entity_id=task.pk, before={}, after={"status": task.status}, request=request)
    return task
