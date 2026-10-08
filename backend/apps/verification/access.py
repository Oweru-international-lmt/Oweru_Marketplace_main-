from django.db.models import Q
from rest_framework.exceptions import PermissionDenied
from apps.properties.policies import get_active_persisted_actor
from apps.leads.policies import management
from .models import VerificationTask


def task_visible(actor, task):
    actor = get_active_persisted_actor(actor)
    if actor is None:
        return False
    if actor.has_role("verifier") and actor.has_marketplace_permission("verification.record_result") and task.job.verifier_id == actor.pk:
        from .conflicts import has_property_conflict
        return not has_property_conflict(actor, task.job.property)
    if task.kind == "LOCAL_OFFICE":
        from apps.local_officials.full_check import can_submit_official
        return actor.has_marketplace_permission("verification.complete_task") and can_submit_official(actor, task)
    if task.kind == "PROFESSIONAL":
        from apps.professionals.services import effective_profile, eligible_professionals
        profile = effective_profile(actor)
        return task.assignee_id == actor.pk and profile is not None and profile.pk in {p.pk for p in eligible_professionals(property_record=task.job.property, professional_type=task.professional_type)}
    return task.kind == "SITE_CAPTURE" and task.assignee_id == actor.pk and actor.has_marketplace_permission("listing.update")


def visible_tasks(actor):
    actor = get_active_persisted_actor(actor)
    if actor is None:
        return VerificationTask.objects.none()
    # Narrow candidate set first; policy remains authoritative for every read.
    candidates = VerificationTask.objects.select_related("job__property__locality", "job__listing").filter(Q(assignee=actor) | Q(job__verifier=actor) | Q(kind="LOCAL_OFFICE", job__property__locality__official_coverage__official__user=actor)).distinct().order_by("due_at", "id")
    return VerificationTask.objects.select_related("job__property__locality").filter(pk__in=[task.pk for task in candidates if task_visible(actor, task)]).order_by("due_at", "id")


def require_task_read(actor, task):
    if not task_visible(actor, task):
        raise PermissionDenied("This task is outside your current assignment or locality.")
    return task
