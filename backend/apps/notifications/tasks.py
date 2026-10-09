from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .services import process_pending, emit, public_link


@shared_task
def deliver_pending_email():
    return process_pending()


@shared_task
def verification_expiry_reminders():
    from apps.lister_identity.models import ListerIdentity
    from apps.verification.models import VerificationJob, PropertyVerification
    now, end = timezone.now(), timezone.now() + timedelta(days=30)
    for identity in ListerIdentity.objects.filter(status="APPROVED", expires_at__gt=now, expires_at__lte=end).select_related("user"):
        emit(event_key=f"identity-expiry:{identity.pk}:{identity.expires_at.isoformat()}", purpose="VERIFICATION_EXPIRING", channels=["screen", "email"], recipient=identity.user, context={"reference": str(identity.pk), "link": public_link("/api/v1/lister-identity/")})
    for job in VerificationJob.objects.filter(status="PASSED", invalidated_at__isnull=True, expires_at__gt=now, expires_at__lte=end).select_related("listing__lister"):
        if job.listing_id:
            emit(event_key=f"verification-expiry:{job.pk}:{job.expires_at.isoformat()}", purpose="VERIFICATION_EXPIRING", channels=["screen", "email"], recipient=job.listing.lister, context={"reference": str(job.pk), "link": public_link(f"/api/v1/full-checks/{job.pk}/")})
    for verification in PropertyVerification.objects.filter(status="APPROVED", expires_at__gt=now, expires_at__lte=end).select_related("property"):
        from apps.accounts.models import User
        recipients = User.objects.filter(is_active=True, listings__property=verification.property).distinct()
        for recipient in recipients:
            emit(event_key=f"property-expiry:{verification.pk}:{verification.expires_at.isoformat()}:{recipient.pk}", purpose="VERIFICATION_EXPIRING", channels=["screen", "email"], recipient=recipient, context={"reference": verification.property.property_id, "link": public_link(f"/api/v1/properties/{verification.property.property_id}/")})
