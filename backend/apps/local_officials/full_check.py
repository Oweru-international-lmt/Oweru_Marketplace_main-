from datetime import timedelta
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.leads.policies import authorize, management
from apps.audit.services import create_audit_log
from apps.verification.conflicts import has_property_conflict
from apps.verification.configuration import setting
from apps.verification.models import VerificationTask, VerificationNotice, TaskAssignment
from .models import OfficialLocalityCoverage
from .services import _active_management_actor, _profile_for_update, _validate_model, is_effective_local_official


# Exact English question text from SRD v1.3 section 14.3. Q2 substitutes owner name.
QUESTIONS = (
    "Is this plot in your Mtaa or village?",
    "Do you know [owner name] as the owner of this plot?",
    "Has this plot been sold or given to anyone else?",
    "Is there any dispute over this plot?",
    "Are the boundaries agreed with the neighbours?",
)


def coverage_manager(actor):
    actor = authorize(actor, "partner.manage")
    if not management(actor):
        raise PermissionDenied("Authorized operational Management is required.")
    return _active_management_actor(actor)


@transaction.atomic
def assign_locality(*, actor, official, locality, starts_at=None, expires_at=None, request=None):
    actor = coverage_manager(actor)
    profile = _profile_for_update(official)
    if not profile.is_active or not is_effective_local_official(profile.user):
        raise ValidationError("An active official profile is required.")
    from apps.localities.models import Locality
    area = Locality.objects.select_for_update().filter(pk=getattr(locality, "pk", locality), approved=True).first()
    if area is None:
        raise ValidationError("An approved canonical street or village is required.")
    row = OfficialLocalityCoverage(official=profile, locality=area, assigned_by=actor, starts_at=starts_at or timezone.now(), expires_at=expires_at)
    _validate_model(row)
    row.save()
    create_audit_log(actor=actor, action="local_official.locality_assigned", entity_type="OfficialLocalityCoverage", entity_id=row.pk, before={}, after={"locality_id": str(area.pk), "official_id": profile.official_id}, request=request)
    route_waiting_tasks(locality=area, actor=actor)
    return row


def eligible_officials(property_record, at=None):
    now = at or timezone.now()
    coverage = OfficialLocalityCoverage.objects.select_related("official__user").filter(
        locality_id=property_record.locality_id, official__is_active=True,
        official__user__is_active=True, revoked_at__isnull=True, starts_at__lte=now,
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now)).order_by("created_at", "id")
    return [row.official for row in coverage if is_effective_local_official(row.official.user) and row.official.user.account_category == "operational" and row.official.user.has_role("local_official") and row.official.user.has_marketplace_permission("verification.complete_task") and not has_property_conflict(row.official.user, property_record)]


def can_submit_official(user, task):
    return task.kind == "LOCAL_OFFICE" and any(profile.user_id == user.pk for profile in eligible_officials(task.job.property))


def route_task(task, actor):
    profiles = eligible_officials(task.job.property)
    if task.due_at is None:
        task.due_at = timezone.now() + timedelta(days=float(setting("official_task_days")))
    task.status = "ASSIGNED" if profiles else "NEEDS_OFFICIAL"
    task.assignee = profiles[0].user if profiles else None
    task.save(update_fields=["status", "assignee", "due_at", "updated_at"])
    if not profiles:
        from apps.accounts.models import User
        for staff in User.objects.filter(is_active=True, account_category="operational", user_roles__role__code="management").distinct():
            if management(staff) and staff.has_marketplace_permission("partner.manage"):
                VerificationNotice.objects.get_or_create(job=task.job, task=task, recipient=staff, phone=staff.phone, purpose="NEEDS_OFFICIAL", defaults={"channels": ["screen", "outbox"]})
    for profile in profiles:
        TaskAssignment.objects.create(task=task, assignee=profile.user, actor=actor, action="ASSIGN")
        VerificationNotice.objects.get_or_create(job=task.job, task=task, recipient=profile.user, phone=profile.user.phone, purpose="OFFICIAL_TASK", defaults={"channels": ["outbox", "screen"]})
    create_audit_log(actor=actor, action="local_official.full_check_routed", entity_type="VerificationTask", entity_id=task.pk, before={}, after={"status": task.status, "locality_id": str(task.job.property.locality_id)}, request=None)


@transaction.atomic
def route_waiting_tasks(*, locality, actor):
    for task in VerificationTask.objects.select_for_update().select_related("job__property").filter(kind="LOCAL_OFFICE", status="NEEDS_OFFICIAL", job__status="IN_PROGRESS", job__property__locality=locality, due_at__gt=timezone.now()):
        route_task(task, actor)


def validate_answers(answers):
    if not isinstance(answers, dict) or set(answers) != {str(n) for n in range(1, 6)}:
        raise ValidationError("Exactly the five SRD questions must be answered.")
    normalized = {}
    for number in range(1, 6):
        item = answers[str(number)]
        if not isinstance(item, dict) or set(item) - {"answer", "comment"} or item.get("answer") not in {"YES", "NO"}:
            raise ValidationError("Each question requires YES or NO and an optional comment.")
        comment = item.get("comment", "")
        if not isinstance(comment, str) or len(comment) > 2000:
            raise ValidationError("Invalid question comment.")
        if number > 1 and not comment.strip():
            raise ValidationError("Questions two through five require a comment as specified by the SRD.")
        normalized[str(number)] = {"question": QUESTIONS[number - 1], "answer": item["answer"], "comment": comment.strip()}
    return normalized


@transaction.atomic
def revoke_locality(*, actor, coverage, request=None):
    actor = coverage_manager(actor)
    row = OfficialLocalityCoverage.objects.select_for_update().get(pk=getattr(coverage, "pk", coverage))
    if row.revoked_at:
        return row
    row.revoked_at = timezone.now()
    row.save()
    from apps.verification.task_services import lock_task
    task_ids = list(VerificationTask.objects.filter(kind="LOCAL_OFFICE", status="ASSIGNED", job__status="IN_PROGRESS", job__property__locality_id=row.locality_id).values_list("pk", flat=True))
    for task_id in task_ids:
        job, task = lock_task(task_id)
        if task.status == "ASSIGNED" and job.status == "IN_PROGRESS":
            route_task(task, actor)
    create_audit_log(actor=actor, action="local_official.locality_revoked", entity_type="OfficialLocalityCoverage", entity_id=row.pk, before={}, after={"locality_id": str(row.locality_id)}, request=request)
    return row
