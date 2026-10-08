from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.leads.policies import authorize
from apps.audit.services import create_audit_log
from .models import PropertyRelationship, VerificationJob, VerificationNotice
from .task_services import lock_task, transition
from .access import require_task_read


@transaction.atomic
def declare_task_relationship(*, actor, task_id, reason, request=None):
    job, task = lock_task(task_id)
    actor = authorize(actor, "verification.complete_task")
    if task.kind not in {"PROFESSIONAL", "LOCAL_OFFICE", "REGISTRY"}:
        raise PermissionDenied("This declaration is for verification partners and the responsible Verifier.")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        raise ValidationError("A bounded relationship declaration is required.")
    existing = PropertyRelationship.objects.filter(property=job.property, user=actor).first()
    if existing:
        # Replay is limited to the same task participant, even after conflict removal.
        if task.assignee_id != actor.pk and not task.assignment_history.filter(assignee=actor).exists() and not task.submissions.filter(author=actor).exists():
            raise PermissionDenied("This declaration is outside your task.")
        return existing
    require_task_read(actor, task)
    declaration = PropertyRelationship.objects.create(property=job.property, user=actor, reason=reason.strip())
    create_audit_log(actor=actor, action="verification.relationship_declared", entity_type="PropertyRelationship", entity_id=declaration.pk, before={}, after={"property_id": job.property.property_id, "reason": reason.strip()}, request=request)
    if task.status == "SUBMITTED" or job.status in {"PASSED", "UNDER_REVIEW"}:
        if not job.invalidated_at:
            job.invalidated_at, job.invalidation_reason = timezone.now(), "Verification participant declared a conflict"
            job.save()
            if job.status != "PASSED":
                transition(job, "NOT_COMPLETED", actor, job.invalidation_reason, request)
            create_audit_log(actor=actor, action="full_check.invalidated", entity_type="VerificationJob", entity_id=job.pk, before={}, after={"reason": "declared_participant_conflict"}, request=request)
    elif task.kind == "PROFESSIONAL":
        task.status, task.assignee, task.due_at = "UNASSIGNED", None, None
        task.save()
    elif task.kind == "LOCAL_OFFICE":
        from apps.local_officials.full_check import route_task
        route_task(task, job.verifier)
    # The same relationship also affects still-live checks using this person's
    # previous submission on the property. Preserve their results and evidence.
    contributed_jobs = VerificationJob.objects.filter(tasks__submissions__author=actor).values("pk")
    affected = VerificationJob.objects.select_for_update().filter(pk__in=contributed_jobs, property=job.property, invalidated_at__isnull=True, status__in=["PASSED", "IN_PROGRESS", "UNDER_REVIEW"]).exclude(pk=job.pk).order_by("pk")
    for prior in affected:
        prior.invalidated_at, prior.invalidation_reason = timezone.now(), "Verification participant declared a conflict"
        prior.save()
        if prior.status != "PASSED":
            transition(prior, "NOT_COMPLETED", actor, prior.invalidation_reason, request)
        create_audit_log(actor=actor, action="full_check.invalidated", entity_type="VerificationJob", entity_id=prior.pk, before={}, after={"reason": "declared_participant_conflict"}, request=request)
    VerificationNotice.objects.get_or_create(job=job, task=task, recipient=job.verifier, purpose="DECLARED_CONFLICT", defaults={"channels": ["screen", "email"]})
    return declaration
