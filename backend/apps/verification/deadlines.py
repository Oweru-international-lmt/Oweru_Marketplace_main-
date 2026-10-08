from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from apps.audit.services import create_audit_log
from .models import VerificationJob, VerificationNotice
from .task_services import lock_job, transition


def process_deadlines(*, at=None):
    now = at or timezone.now()
    candidates = VerificationJob.objects.filter(
        Q(status="AWAITING_CONSENT") | Q(status="IN_PROGRESS") | Q(status="PASSED", expires_at__lte=now, invalidated_at__isnull=True)
    ).values_list("pk", flat=True)
    count = 0
    for job_id in list(candidates):
        with transaction.atomic():
            job = lock_job(job_id)
            reason = ""
            if job.status == "AWAITING_CONSENT":
                if not job.owner_phone and job.contact_due_at and job.contact_due_at <= now:
                    reason = "Owner contact deadline elapsed"
                elif job.consent_due_at and job.consent_due_at <= now:
                    reason = "Owner consent reply deadline elapsed"
            elif job.status == "IN_PROGRESS":
                timed_out = list(job.tasks.select_for_update().exclude(status="SUBMITTED").filter(due_at__lte=now))
                for task in timed_out:
                    task.status = "TIMED_OUT"
                    task.save()
                    create_audit_log(actor=None, action="verification.task_timed_out", entity_type="VerificationTask", entity_id=task.pk, before={}, after={"kind": task.kind}, request=None)
                if timed_out:
                    reason = "Required verification task deadline elapsed"
            elif job.status == "PASSED" and job.expires_at and job.expires_at <= now and not job.invalidated_at:
                from apps.audit.models import AuditLog
                if not AuditLog.objects.filter(action="full_check.expired", entity_id=str(job.pk), after__expires_at=job.expires_at.isoformat()).exists():
                    create_audit_log(actor=None, action="full_check.expired", entity_type="VerificationJob", entity_id=job.pk, before={}, after={"expires_at": job.expires_at.isoformat()}, request=None)
                    from .levels import recalculate_levels
                    recalculate_levels(property_id=job.property_id, at=now)
                    create_audit_log(actor=None, action="verification.level_recalculated", entity_type="PropertyRecord", entity_id=job.property_id, before={}, after={"reason": "full_check_expired"}, request=None)
                    count += 1
            if reason:
                transition(job, "NOT_COMPLETED", None, reason)
                VerificationNotice.objects.get_or_create(job=job, recipient=job.buyer, phone=job.buyer.phone, purpose="FULL_CHECK_NOT_COMPLETED", defaults={"channels": ["screen", "email", "outbox"]})
                count += 1
    return count


@transaction.atomic
def invalidate_full_checks(*, property_record, actor, reason, request=None):
    from apps.properties.models import PropertyRecord
    PropertyRecord.objects.select_for_update().get(pk=property_record.pk)
    now = timezone.now()
    jobs = list(VerificationJob.objects.select_for_update().filter(property=property_record, invalidated_at__isnull=True).exclude(status__in=["PROBLEM_FOUND", "NOT_COMPLETED"]).order_by("id"))
    for job in jobs:
        job.invalidated_at, job.invalidation_reason = now, reason
        job.save()
        if job.status != "PASSED":
            transition(job, "NOT_COMPLETED", actor, reason, request)
        create_audit_log(actor=actor, action="full_check.invalidated", entity_type="VerificationJob", entity_id=job.pk, before={}, after={"reason": reason}, request=request)
    if jobs:
        create_audit_log(actor=actor, action="verification.level_recalculated", entity_type="PropertyRecord", entity_id=property_record.pk, before={}, after={"reason": reason}, request=request)
    return jobs
