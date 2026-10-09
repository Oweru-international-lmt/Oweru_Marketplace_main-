from datetime import timedelta
from string import Formatter
from urllib.parse import quote
from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.audit.services import create_audit_log
from apps.leads.policies import authorize, management
from apps.payments.idempotency import Conflict
from apps.verification.configuration import setting
from .catalog import DEFAULTS, CATALOG
from .models import Notification, MessageTemplate, TemplateHistory, DeliveryAttempt


def public_link(path):
    return getattr(settings, "MARKETPLACE_PUBLIC_URL", "").rstrip("/") + path


def render(purpose, language, context):
    if purpose not in DEFAULTS or language not in {"sw", "en"}:
        raise ValidationError("Unknown message purpose or language.")
    template = MessageTemplate.objects.filter(key=purpose).first()
    text = getattr(template, language) if template else DEFAULTS[purpose][language]
    values = {"reference": "", "link": "", "details": "", **context}
    return text.format(**values).strip(), template.version if template else 0


@transaction.atomic
def emit(*, event_key, purpose, channels, recipient=None, phone="", email="", name="", language=None, context=None, actor=None, source=None, expires_at=None):
    if set(channels) - set(Notification.CHANNELS):
        raise ValidationError("Unsupported notification channel.")
    language = language or (recipient.preferred_language if recipient else "sw")
    phone, email, name = phone or (recipient.phone if recipient else ""), email or (recipient.email if recipient else ""), name or (recipient.full_name if recipient else "")
    context = context or {}
    message, version = render(purpose, language, context)
    rows = []
    for channel in channels:
        if channel == "email" and not email or channel in {"outbox", "self_service"} and not phone:
            continue
        row, created = Notification.objects.get_or_create(event_key=event_key, channel=channel, defaults={"purpose": purpose, "recipient": recipient, "phone": phone, "email": email, "recipient_name": name, "language": language, "context": context, "message": message, "template_version": version, "created_by": actor, "source_type": type(source).__name__ if source else "", "source_id": source.pk if source else None, "expires_at": expires_at})
        if created:
            create_audit_log(actor=actor, action="notification.created", entity_type="Notification", entity_id=row.pk, after={"purpose": purpose, "channel": channel})
        rows.append(row)
    return rows


class SMTPAdapter:
    def deliver(self, row):
        if row.context.get("link", "").startswith("/"):
            raise ValidationError("MARKETPLACE_PUBLIC_URL must be configured before external delivery.")
        subject = CATALOG[row.purpose][1 if row.language == "sw" else 0]
        result = EmailMessage(subject, row.message, settings.DEFAULT_FROM_EMAIL, [row.email], headers={"Message-ID": f"<oweru-{row.pk}@marketplace>"}).send(fail_silently=False)
        if result != 1:
            raise RuntimeError("Email provider did not accept the message.")


@transaction.atomic
def deliver_email(notification_id, adapter=None):
    # Retain the row lock during provider submission: concurrent workers cannot submit twice.
    row = get_object_or_404(Notification.objects.select_for_update(), pk=notification_id)
    if row.channel != "email":
        raise ValidationError("Background delivery only sends email.")
    if row.status in {"SENT", "CANCELLED"} or row.retry_at and row.retry_at > timezone.now() or row.attempts >= int(setting("email_max_attempts")):
        return row
    if row.expires_at and row.expires_at <= timezone.now() or row.recipient_id and not row.recipient.is_active:
        row.status = "CANCELLED"
        row.save(update_fields=["status", "updated_at"])
        return row
    row.attempts += 1
    try:
        (adapter or SMTPAdapter()).deliver(row)
    except Exception as exc:
        row.status = "FAILED"
        row.retry_at = timezone.now() + timedelta(seconds=min(3600, 60 * 2 ** min(row.attempts - 1, 6)))
        error = type(exc).__name__[:100]
        success = False
    else:
        row.status, row.sent_at, row.retry_at = "SENT", timezone.now(), None
        error, success = "", True
    row.save()
    DeliveryAttempt.objects.create(notification=row, attempt=row.attempts, successful=success, error_type=error)
    create_audit_log(action="notification.email_sent" if success else "notification.email_failed", entity_type="Notification", entity_id=row.pk, after={"attempt": row.attempts, "error_type": error})
    return row


def process_pending(limit=100, adapter=None):
    ids = list(Notification.objects.filter(channel="email", status__in=["WAITING", "FAILED"], attempts__lt=int(setting("email_max_attempts"))).filter(Q(retry_at__isnull=True) | Q(retry_at__lte=timezone.now())).order_by("created_at").values_list("pk", flat=True)[:limit])
    for pk in ids:
        deliver_email(pk, adapter)
    return len(ids)


def outbox_actor(actor):
    actor = authorize(actor, "outbox.send")
    if actor.account_category != "operational" or not any(actor.has_role(role) for role in ["management", "verifier", "marketer"]):
        raise PermissionDenied("Active authorized Oweru staff are required.")
    return actor


def outbox_payload(row, request):
    message = row.message
    if row.status != "SENT" and (row.expires_at and row.expires_at <= timezone.now() or row.recipient_id and not row.recipient.is_active):
        return None
    if row.source_type == "ConfirmationDelivery" and row.status != "SENT":
        from apps.payments.models import ConfirmationDelivery
        from apps.payments.views import settings_confirmation_link
        from urllib.parse import urlencode
        source = get_object_or_404(ConfirmationDelivery, pk=row.source_id)
        if source.consumed_at or source.expires_at <= timezone.now():
            return None
        link = settings_confirmation_link(source, urlencode)
        import json
        message, _ = render(row.purpose, row.language, {"reference": source.context.get("property_id", source.context.get("deal_id", "")), "details": json.dumps(source.context, ensure_ascii=False), "link": link})
    elif row.status != "SENT" and row.purpose == "PROFESSIONAL_LOGIN" and row.source_type == "VerificationNotice":
        from apps.verification.models import VerificationNotice
        from apps.verification.outbox import message as legacy_message
        source = get_object_or_404(VerificationNotice, pk=row.source_id)
        setup = legacy_message(source, request)["message"]
        message, _ = render(row.purpose, row.language, {"details": source.recipient.email, "link": setup.rsplit(" ", 1)[-1]})
    return {"id": str(row.pk), "recipient_name": row.recipient_name, "phone": row.phone, "purpose": row.purpose, "message": message, "language": row.language, "created_at": row.created_at, "created_by": str(row.created_by_id) if row.created_by_id else None, "sent_by": str(row.sent_by_id) if row.sent_by_id else None, "sent_at": row.sent_at, "status": row.status, "overdue": working_hours(row.created_at, timezone.now()) >= float(setting("outbox_waiting_hours")), "whatsapp_link": f"https://wa.me/{row.phone.lstrip('+')}?text={quote(message)}"}


def working_hours(start, end):
    # Skip weekends. Staff shifts are not specified by the SRD; report this calendar limit.
    current, end = timezone.localtime(start), timezone.localtime(end)
    seconds = 0
    while current < end:
        next_day = (current + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        stop = min(next_day, end)
        if current.weekday() < 5:
            seconds += (stop - current).total_seconds()
        current = stop
    return seconds / 3600


@transaction.atomic
def mark_sent(*, actor, notification_id, request=None):
    actor = outbox_actor(actor)
    # Match legacy -> central lock order used by post_save integration.
    initial = get_object_or_404(Notification, pk=notification_id)
    source_already_sent = None
    if initial.channel != "outbox":
        raise ValidationError("Only staff outbox messages can be manually marked sent.")
    payload = outbox_payload(initial, request)
    if payload is None:
        raise ValidationError("Message expired, consumed, or recipient inactive.")
    if initial.source_type == "ConfirmationDelivery":
        from apps.payments.models import ConfirmationDelivery
        source = get_object_or_404(ConfirmationDelivery.objects.select_for_update(), pk=initial.source_id)
        source_already_sent = source.sent_at is not None
        if source.consumed_at or source.expires_at <= timezone.now():
            raise ValidationError("Confirmation is no longer usable.")
        if source.sent_at is None:
            source.sent_at, source.sent_by = timezone.now(), actor
            source.save(update_fields=["sent_at", "sent_by", "updated_at"])
    elif initial.source_type == "VerificationNotice":
        from apps.verification.models import VerificationNotice
        source = get_object_or_404(VerificationNotice.objects.select_for_update(), pk=initial.source_id)
        source_already_sent = source.sent_at is not None
        if source.sent_at is None:
            source.sent_at, source.sent_by = timezone.now(), actor
            source.save(update_fields=["sent_at", "sent_by", "updated_at"])
    row = get_object_or_404(Notification.objects.select_for_update(), pk=notification_id)
    already_sent = source_already_sent if source_already_sent is not None else row.sent_at is not None
    if row.expires_at and row.expires_at <= timezone.now() or row.recipient_id and not row.recipient.is_active:
        raise ValidationError("Message expired or recipient inactive.")
    if row.status == "CANCELLED":
        raise ValidationError("Message cancelled.")
    if row.sent_at is None:
        row.sent_at, row.sent_by, row.status = timezone.now(), actor, "SENT"
        row.save(update_fields=["sent_at", "sent_by", "status", "updated_at"])
    if not already_sent:
        row.message = payload["message"]
        row.save(update_fields=["message", "updated_at"])
        create_audit_log(actor=actor, action="notification.outbox_sent", entity_type="Notification", entity_id=row.pk, after={"purpose": row.purpose}, request=request)
    return row


def send_account_email(*, user, purpose, link):
    """Preserve the existing immediate account-email contract with central delivery logging."""
    import secrets
    row = emit(event_key=f"account-email:{secrets.token_hex(16)}", purpose=purpose, channels=["email"], recipient=user, context={"link": link})[0]
    delivered = deliver_email(row.pk)
    if delivered.status != "SENT":
        raise RuntimeError("Account email delivery failed; the central outbox retains its retry status.")
    return delivered


@transaction.atomic
def change_template(*, actor, key, en, sw, version, request=None):
    actor = authorize(actor, "settings.manage")
    if not management(actor) or key not in DEFAULTS:
        raise PermissionDenied("Management and a catalogued template are required.")
    for text in [en, sw]:
        if not isinstance(text, str) or not text.strip() or len(text) > 10000:
            raise ValidationError("Both bounded language variants are required.")
        try:
            fields = [name for _, name, spec, conversion in Formatter().parse(text) if name is not None]
            if set(fields) - {"reference", "details", "link"} or "link" not in fields:
                raise ValueError()
            text.format(reference="reference", details="details", link="link")
        except (ValueError, KeyError, IndexError, AttributeError):
            raise ValidationError("Only reference, details and link placeholders are allowed; link is required.")
    from apps.free_checks.services import lock_phone
    lock_phone("template:" + key)
    row = MessageTemplate.objects.select_for_update().filter(key=key).first()
    current = row.version if row else 0
    if version != current:
        raise Conflict("Template changed; refresh before editing.")
    if row is None:
        row = MessageTemplate(key=key)
    row.en, row.sw, row.version, row.changed_by = en, sw, current + 1, actor
    row.save()
    TemplateHistory.objects.create(template=row, version=row.version, en=en, sw=sw, actor=actor)
    create_audit_log(actor=actor, action="notification.template_changed", entity_type="MessageTemplate", entity_id=row.pk, after={"key": key, "version": row.version}, request=request)
    return row
