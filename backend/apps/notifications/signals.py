"""Bridge existing durable domain intents; do not replace confirmation tokens."""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from apps.verification.models import VerificationNotice
from apps.payments.models import FinancialNotice, ConfirmationDelivery, Payout
from apps.complaints.models import ComplaintNotice
from apps.free_checks.models import FreeCheckReport
from apps.audit.models import AuditLog
from .models import Notification
from .services import emit, public_link
from .catalog import DEFAULTS


@receiver(post_save, sender=VerificationNotice)
def verification_notice(sender, instance, created, **kwargs):
    if not created:
        if instance.sent_at:
            Notification.objects.filter(source_type="VerificationNotice", source_id=instance.pk, channel="outbox", sent_at__isnull=True).update(sent_at=instance.sent_at, sent_by=instance.sent_by, status="SENT")
        return
    purpose = "TASK_ASSIGNED" if instance.task_id and instance.purpose not in DEFAULTS else instance.purpose
    if purpose not in DEFAULTS:
        purpose = "TASK_ASSIGNED" if instance.task_id else "NEEDS_OFFICIAL"
    path = f"/api/v1/verification-tasks/{instance.task_id}/" if instance.task_id else f"/api/v1/full-checks/{instance.job_id}/" if instance.job_id else ""
    emit(event_key=f"verification:{instance.pk}", purpose=purpose, channels=instance.channels, recipient=instance.recipient, phone=instance.phone, context={"reference": str(instance.task_id or instance.job_id or ""), "link": public_link(path) if path else ""}, source=instance)


@receiver(post_save, sender=FinancialNotice)
def financial_notice(sender, instance, created, **kwargs):
    if created and instance.purpose in DEFAULTS:
        path = f"/api/v1/deals/{instance.deal_id}/" if instance.deal_id else f"/api/v1/leads/{instance.lead_id}/"
        emit(event_key=f"finance:{instance.pk}", purpose=instance.purpose, channels=["screen", "email"], recipient=instance.recipient, context={"reference": str(instance.deal_id or instance.lead_id), "link": public_link(path)}, source=instance)


@receiver(post_save, sender=ConfirmationDelivery)
def confirmation(sender, instance, created, **kwargs):
    if created and instance.purpose in DEFAULTS:
        emit(event_key=f"confirmation:{instance.pk}", purpose=instance.purpose, channels=["outbox"], recipient=instance.user, phone=instance.recipient, context={}, source=instance, expires_at=instance.expires_at)
    elif not created:
        if instance.consumed_at:
            Notification.objects.filter(source_type="ConfirmationDelivery", source_id=instance.pk, status__in=["WAITING", "FAILED"]).update(status="CANCELLED")
        elif instance.sent_at:
            Notification.objects.filter(source_type="ConfirmationDelivery", source_id=instance.pk, channel="outbox", sent_at__isnull=True).update(sent_at=instance.sent_at, sent_by=instance.sent_by, status="SENT")


@receiver(post_save, sender=ComplaintNotice)
def complaint_notice(sender, instance, created, **kwargs):
    if not created:
        return
    row = instance.complaint
    from apps.complaints.services import token_for
    link = public_link(f"/api/v1/complaints/{row.pk}/status/?token={token_for(row)}")
    emit(event_key=f"complaint:{instance.pk}", purpose=instance.purpose, channels=instance.channels, phone=row.phone, email=row.email, name=row.name, language=row.language, actor=row.created_by, context={"reference": row.reference, "details": f"{row.status}. {row.outcome} {row.reasons}".strip(), "link": link}, source=instance)


@receiver(post_save, sender=FreeCheckReport)
def free_report(sender, instance, created, **kwargs):
    if not created:
        return
    row = instance.free_check
    from apps.free_checks.services import token_for
    link = public_link(f"/api/v1/free-checks/{row.pk}/?token={token_for(row)}")
    emit(event_key=f"free-report:{instance.pk}", purpose="FREE_CHECK_REPORT", channels=["screen", "self_service"] + (["email"] if row.email else []), phone=row.phone, email=row.email, language=row.language, context={"reference": row.reference, "link": link}, source=instance, expires_at=row.expires_at)


@receiver(post_save, sender=AuditLog)
def identity_events(sender, instance, created, **kwargs):
    if not created or instance.action not in {"LISTER_IDENTITY_SUBMITTED", "LISTER_IDENTITY_APPROVED", "LISTER_IDENTITY_REJECTED"}:
        return
    from apps.lister_identity.models import ListerIdentity
    row = ListerIdentity.objects.filter(pk=instance.entity_id).select_related("user").first()
    if row is None:
        return
    if instance.action == "LISTER_IDENTITY_SUBMITTED":
        from apps.payments.confirmations import queue_identity_phone_confirmation
        queue_identity_phone_confirmation(row.user)
    else:
        emit(event_key=f"identity:{instance.pk}", purpose="IDENTITY_DECISION", channels=["screen", "email"], recipient=row.user, actor=instance.actor, context={"reference": str(row.pk), "details": row.status, "link": public_link("/api/v1/lister-identity/")}, source=instance)


@receiver(post_save, sender=Payout)
def payout(sender, instance, created, **kwargs):
    if instance.status == "PAID":
        emit(event_key=f"payout-paid:{instance.pk}", purpose="PAYOUT_PAID", channels=["screen", "email"], recipient=instance.agent, actor=instance.paid_by, context={"reference": str(instance.pk), "link": public_link(f"/api/v1/payouts/{instance.pk}/")}, source=instance)
