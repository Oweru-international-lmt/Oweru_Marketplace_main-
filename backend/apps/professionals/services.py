import secrets
from datetime import timedelta
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from apps.accounts.models import User
from apps.audit.services import create_audit_log
from apps.leads.policies import authorize, management
from apps.localities.models import District, Region
from apps.roles.services import assign_role
from apps.roles.legacy_authorization.services import _assign, _role
from apps.verification.conflicts import has_property_conflict
from apps.verification.configuration import setting
from apps.verification.models import TaskAssignment, VerificationTask, VerificationNotice
from .models import ProfessionalProfile


def require_manager(actor):
    actor = authorize(actor, "partner.manage")
    if not management(actor):
        raise PermissionDenied("Management is required.")
    return actor


def validate_profile(profile):
    try:
        profile.full_clean()
    except DjangoValidationError as exc:
        raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc


def profile_audit_state(profile):
    return {"status": profile.status, "professional_type": profile.professional_type, "registration_number": profile.registration_number, "regions": [str(pk) for pk in profile.regions.values_list("pk", flat=True)], "districts": [str(pk) for pk in profile.districts.values_list("pk", flat=True)]}


def _coverage(regions, districts):
    region_ids = [getattr(item, "pk", item) for item in regions]
    district_ids = [getattr(item, "pk", item) for item in districts]
    region_rows = list(Region.objects.filter(pk__in=region_ids))
    district_rows = list(District.objects.filter(pk__in=district_ids))
    if not region_ids and not district_ids or len(region_rows) != len(set(region_ids)) or len(district_rows) != len(set(district_ids)):
        raise ValidationError("At least one canonical region or district is required; coverage identifiers must exist.")
    return region_rows, district_rows


@transaction.atomic
def register_professional(*, actor, professional_type, registration_number, national_id_number, regions=(), districts=(), user=None, email=None, phone=None, full_name=None, request=None):
    actor = require_manager(actor)
    if professional_type not in ProfessionalProfile.Type.values:
        raise ValidationError("Unsupported professional type.")
    if not isinstance(registration_number, str) or not registration_number.strip() or not isinstance(national_id_number, str) or not national_id_number.strip():
        raise ValidationError("Registration number and national ID are required.")
    region_rows, district_rows = _coverage(regions, districts)
    if user is None:
        if not email or not phone or not full_name:
            raise ValidationError("Email, WhatsApp number and name are required.")
        # Reuse existing password reset; never transmit a reusable password.
        user = User(email=email, phone=phone, full_name=full_name, account_category="operational")
        user.set_password(secrets.token_urlsafe(48))
        validate_profile(user)
        user.save()
    else:
        user = User.objects.select_for_update().filter(pk=getattr(user, "pk", user), is_active=True, account_category="operational").first()
        if user is None:
            raise ValidationError("An active operational account is required; public accounts cannot be converted.")
    if ProfessionalProfile.objects.filter(user=user).exists():
        raise ValidationError("Professional profile already exists.")
    if not user.full_name.strip() or not user.phone or not user.email:
        raise ValidationError("The Professional account must have its name, WhatsApp number and email address.")
    assign_role(user=user, role_code="professional", assigned_by=actor, request=request)
    _assign(user, _role("professional"), actor, request)
    profile = ProfessionalProfile(user=user, professional_type=professional_type, registration_number=registration_number.strip(), national_id_number=national_id_number.strip(), verified_by=actor, verified_at=timezone.now())
    validate_profile(profile)
    profile.save()
    profile.regions.set(region_rows)
    profile.districts.set(district_rows)
    VerificationNotice.objects.get_or_create(recipient=user, phone=user.phone, purpose="PROFESSIONAL_LOGIN", defaults={"channels": ["outbox"]})
    create_audit_log(actor=actor, action="professional.registered", entity_type="ProfessionalProfile", entity_id=profile.pk, before={}, after={"professional_type": professional_type, "user_id": str(user.pk)}, request=request)
    return profile


@transaction.atomic
def update_professional(*, actor, profile_id, status=None, regions=None, districts=None, registration_number=None, reason="", request=None):
    actor = require_manager(actor)
    profile = ProfessionalProfile.objects.select_for_update().select_related("user").filter(pk=profile_id).first()
    if profile is None:
        raise NotFound("Professional profile not found.")
    before = profile_audit_state(profile)
    if status is not None:
        if status not in {"ACTIVE", "INACTIVE"} or not reason.strip():
            raise ValidationError("A supported status and reason are required.")
        profile.status = status
    if registration_number is not None:
        profile.registration_number = registration_number.strip()
    if regions is not None or districts is not None:
        r, d = _coverage(regions if regions is not None else profile.regions.all(), districts if districts is not None else profile.districts.all())
        profile.regions.set(r)
        profile.districts.set(d)
    validate_profile(profile)
    profile.save()
    create_audit_log(actor=actor, action="professional.profile_changed", entity_type="ProfessionalProfile", entity_id=profile.pk, before=before, after=profile_audit_state(profile), request=request)
    return profile


def effective_profile(user):
    try:
        actor = authorize(user, "verification.complete_task")
    except PermissionDenied:
        return None
    if not actor.has_role("professional"):
        return None
    return ProfessionalProfile.objects.filter(user=actor, status="ACTIVE").first()


def eligible_professionals(*, property_record, professional_type):
    if professional_type not in ProfessionalProfile.Type.values:
        raise ValidationError("Unsupported professional type.")
    candidates = ProfessionalProfile.objects.select_related("user").filter(status="ACTIVE", professional_type=professional_type).filter(Q(districts=property_record.district) | Q(regions=property_record.region)).distinct().order_by("registration_number")
    return [profile for profile in candidates if effective_profile(profile.user) and not has_property_conflict(profile.user, property_record)]


@transaction.atomic
def assign_professional(*, actor, task_id, profile_id, request=None):
    from apps.verification.task_services import lock_task, require_responsible_verifier, require_work
    job, task = lock_task(task_id)
    actor = require_responsible_verifier(actor, job, "verification.assign_task")
    require_work(job)
    if task.kind != "PROFESSIONAL" or task.status not in {"UNASSIGNED", "TIMED_OUT"}:
        raise ValidationError("Only unassigned professional tasks may be assigned.")
    profile = ProfessionalProfile.objects.select_for_update().select_related("user").filter(pk=profile_id).first()
    if profile is None:
        raise NotFound("Professional profile not found.")
    if profile.pk not in {item.pk for item in eligible_professionals(property_record=job.property, professional_type=task.professional_type)}:
        raise PermissionDenied("Professional type, active status, district coverage and conflict policy must all qualify.")
    task.assignee, task.status = profile.user, "ASSIGNED"
    task.due_at = timezone.now() + timedelta(days=float(setting("professional_task_days")))
    task.save()
    TaskAssignment.objects.create(task=task, assignee=profile.user, actor=actor, action="ASSIGN")
    VerificationNotice.objects.get_or_create(job=job, task=task, recipient=profile.user, phone=profile.user.phone, purpose="PROFESSIONAL_TASK", defaults={"channels": ["outbox", "screen"]})
    create_audit_log(actor=actor, action="professional.task_assigned", entity_type="VerificationTask", entity_id=task.pk, before={}, after={"professional_id": str(profile.pk)}, request=request)
    return task


@transaction.atomic
def decide_task(*, actor, task_id, decision, reason="", request=None):
    from apps.verification.task_services import lock_task, require_work
    job, task = lock_task(task_id)
    actor = authorize(actor, "verification.complete_task")
    require_work(job)
    profile = effective_profile(actor)
    if profile is None or task.assignee_id != actor.pk or task.kind != "PROFESSIONAL" or has_property_conflict(actor, job.property):
        raise PermissionDenied("Only the eligible assigned professional may decide.")
    if profile.pk not in {item.pk for item in eligible_professionals(property_record=job.property, professional_type=task.professional_type)}:
        raise PermissionDenied("Current geographic coverage and professional type are required.")
    if task.status != "ASSIGNED" or not task.due_at or task.due_at <= timezone.now() or decision not in {"ACCEPT", "DECLINE"}:
        raise ValidationError("Only a live assigned task may be accepted or declined.")
    task.status = "ACCEPTED" if decision == "ACCEPT" else "UNASSIGNED"
    TaskAssignment.objects.create(task=task, assignee=actor, actor=actor, action=decision, reason=reason.strip())
    if decision == "DECLINE":
        task.assignee, task.due_at = None, None
        VerificationNotice.objects.get_or_create(job=job, task=task, recipient=job.verifier, purpose="PROFESSIONAL_DECLINED", defaults={"channels": ["screen", "email"]})
    task.save()
    create_audit_log(actor=actor, action="professional.task_accepted" if decision == "ACCEPT" else "professional.task_declined", entity_type="VerificationTask", entity_id=task.pk, before={}, after={"status": task.status}, request=request)
    return task
