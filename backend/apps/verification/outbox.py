"""Staff-mediated Phase 1 WhatsApp delivery, using existing account tokens."""
from urllib.parse import urlencode, quote
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from apps.leads.policies import authorize, management
from .models import VerificationNotice
from .full_check_services import audit


def staff(actor):
    actor = authorize(actor, "outbox.send")
    if not management(actor):
        raise PermissionDenied("Authorized Oweru Management is required.")
    return actor


def message(row, request):
    payload = {"id": str(row.pk), "recipient": row.phone, "purpose": row.purpose, "channels": row.channels, "sent_at": row.sent_at}
    if row.purpose == "PROFESSIONAL_LOGIN":
        if not settings.PASSWORD_RESET_URL:
            raise ValidationError("PASSWORD_RESET_URL must be configured before delivering login details.")
        if not row.recipient or not row.recipient.is_active:
            raise ValidationError("The Professional account is inactive.")
        values = {"uid": urlsafe_base64_encode(force_bytes(row.recipient.pk)), "token": default_token_generator.make_token(row.recipient)}
        link = settings.PASSWORD_RESET_URL + ("&" if "?" in settings.PASSWORD_RESET_URL else "?") + urlencode(values)
        payload["message"] = f"Oweru Marketplace: your login email is {row.recipient.email}. Set your password securely: {link}"
    elif row.purpose == "FULL_CHECK_REPORT_READY":
        report = row.job.reports.order_by("-version").first()
        if report is None:
            raise ValidationError("The authoritative report has not been generated.")
        # An authenticated download route, never a publicly transferable evidence key.
        path = f"/api/v1/full-checks/{row.job_id}/reports/{report.pk}/"
        link = request.build_absolute_uri(path)
        payload["message"] = f"Oweru Marketplace: your Full Check report is ready. Sign in to download: {link}"
        payload["download_path"] = path
    elif row.task_id:
        payload["message"] = f"Oweru Marketplace: {row.purpose.replace('_', ' ').lower()}. Sign in and open your verification task {row.task_id}."
        payload["task_id"] = str(row.task_id)
    else:
        payload["message"] = f"Oweru Marketplace: {row.purpose.replace('_', ' ').lower()}. Sign in to review Full Check {row.job_id}."
    phone = row.phone or (row.recipient.phone if row.recipient else "")
    payload["recipient"] = phone
    if phone:
        payload["whatsapp_link"] = f"https://wa.me/{phone.lstrip('+')}?text={quote(payload['message'])}"
    return payload


class VerificationOutboxView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        actor = staff(request.user)
        rows = VerificationNotice.objects.filter(sent_at__isnull=True, channels__contains=["outbox"]).select_related("recipient", "job").order_by("created_at")[:100]
        audit(actor, "sensitive_data.accessed", actor, {"purpose": "verification_outbox"}, request)
        return Response([message(row, request) for row in rows])


class VerificationNoticeSentView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, notice_id):
        if request.data:
            raise ValidationError("This action takes no client-controlled delivery fields.")
        actor = staff(request.user)
        row = get_object_or_404(VerificationNotice.objects.select_for_update(), pk=notice_id)
        if "outbox" not in row.channels:
            raise ValidationError("This notice is not a staff-delivery item.")
        if row.sent_at is None:
            row.sent_at, row.sent_by = timezone.now(), actor
            row.save(update_fields=["sent_at", "sent_by", "updated_at"])
            audit(actor, "verification.notice_sent", row, {"purpose": row.purpose}, request)
        return Response({"id": str(row.pk), "sent_at": row.sent_at})
