import re
from datetime import timedelta
from urllib.parse import urlencode
from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError as ModelValidationError
from django.db import transaction
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied
from apps.accounts.models import User
from apps.audit.services import create_audit_log
from apps.leads.policies import authorize
from apps.payments.idempotency import Conflict
from .models import MarketingConsent, ConsentHistory, FeaturedListing, Content, Campaign, CampaignDelivery, CampaignAttempt


def staff(actor, permission="marketing.manage"):
    actor = authorize(actor, permission)
    if actor.account_category != "operational" or not (actor.has_role("marketer") or actor.has_role("management")):
        raise PermissionDenied("Marketing staff are required.")
    return actor


def tagged_link(path, source):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", source or ""):
        raise ValidationError("A bounded source tag is required.")
    if not path.startswith("/") or path.startswith("//") or any(c in path for c in "\\%?#\r\n") or any(ord(c) < 32 for c in path):
        raise ValidationError("Use a local path without query or fragment.")
    return settings.MARKETPLACE_PUBLIC_URL.rstrip("/") + path + "?" + urlencode({"source_tag": source})


def validate_model(row):
    try:
        row.full_clean()
    except ModelValidationError as exc:
        raise ValidationError(getattr(exc, "message_dict", exc.messages)) from exc


def validate_copy(values):
    for key, value in values.items():
        if key.startswith(("title_", "subject_", "body_")):
            if not value.strip() or len(value) > 10000 or re.search(r"<[^>]*>|guarantee", value, re.I) or "\r" in value or (key.startswith("subject_") and "\n" in value):
                raise ValidationError({key: "Use bounded plain text and approved wording."})


@transaction.atomic
def consent(*, actor, agreed, policy_version, version):
    actor = authorize(actor, "account.update")
    # User lock serializes first opt-in and delivery with withdrawal.
    actor = User.objects.select_for_update().get(pk=actor.pk)
    authorize(actor, "account.update")
    row = MarketingConsent.objects.select_for_update().filter(user=actor).first()
    if version != (row.version if row else 0):
        raise Conflict("Consent changed; refresh before editing.")
    row = row or MarketingConsent(user=actor, version=0)
    row.agreed, row.version = agreed, row.version + 1
    row.save()
    ConsentHistory.objects.create(consent=row, agreed=agreed, version=row.version, policy_version=policy_version)
    create_audit_log(actor=actor, action="marketing.consent_changed", entity_type="MarketingConsent", entity_id=row.pk, after={"agreed": agreed, "version": row.version, "policy_version": policy_version})
    return row


@transaction.atomic
def save_item(*, actor, model, values, item_id=None, version=0, request=None):
    actor = staff(actor)
    row = get_object_or_404(model.objects.select_for_update(), pk=item_id) if item_id else model()
    if version != (row.version if item_id else 0):
        raise Conflict("Marketing item changed; refresh before editing.")
    if values["ends_at"] <= values["starts_at"]:
        raise ValidationError("End must follow start.")
    validate_copy(values)
    if model is Content:
        tagged_link(values["target_path"], values["source_tag"])
    else:
        from apps.listings.services import get_public_listing
        values["listing"] = get_public_listing(listing_id=values.pop("listing_id"))
    for key, value in values.items():
        setattr(row, key, value)
    row.version = version + 1
    validate_model(row)
    row.save()
    create_audit_log(actor=actor, action="marketing.item_saved", entity_type=model.__name__, entity_id=row.pk, after={"version": row.version}, request=request)
    return row


@transaction.atomic
def create_campaign(*, actor, values, request=None):
    actor = staff(actor, "marketing.send_campaign")
    validate_copy(values)
    tagged_link(values["target_path"], values["source_tag"])
    if Campaign.objects.filter(source_tag=values["source_tag"]).exists():
        raise Conflict("Source tag already belongs to a campaign.")
    row = Campaign(created_by=actor, **values)
    validate_model(row)
    row.save()
    recipients = User.objects.filter(is_active=True, marketingconsent__agreed=True)
    CampaignDelivery.objects.bulk_create([CampaignDelivery(campaign=row, recipient=user) for user in recipients.iterator()], batch_size=500)
    create_audit_log(actor=actor, action="marketing.campaign_created", entity_type="Campaign", entity_id=row.pk, after={"source_tag": row.source_tag, "recipients": row.deliveries.count()}, request=request)
    return row


def delivery_token(row):
    return signing.dumps(str(row.pk), salt="marketing-click")


@transaction.atomic
def deliver(delivery_id):
    initial = get_object_or_404(CampaignDelivery, pk=delivery_id)
    user = User.objects.select_for_update().get(pk=initial.recipient_id)
    row = CampaignDelivery.objects.select_for_update().select_related("campaign").get(pk=delivery_id)
    if row.status != "WAITING" or row.next_attempt_at and row.next_attempt_at > timezone.now():
        return row
    if not user.is_active or not MarketingConsent.objects.filter(user=user, agreed=True).exists():
        row.status = "CANCELLED"
        row.save(update_fields=["status", "updated_at"])
        return row
    language = user.preferred_language
    campaign = row.campaign
    root = settings.MARKETPLACE_PUBLIC_URL.rstrip("/")
    link = root + "/api/v1/marketing/click/?" + urlencode({"token": delivery_token(row)})
    preferences = root + "/api/v1/marketing/consent/"
    message = getattr(campaign, "body_" + language) + "\n\n" + link + "\n\n" + ("Manage marketing consent: " if language == "en" else "Dhibiti ruhusa ya masoko: ") + preferences
    row.attempts += 1
    try:
        if not root.startswith("https://"):
            raise ValidationError("Configure an HTTPS Marketplace URL before campaign delivery.")
        from apps.notifications.services import SMTPAdapter
        SMTPAdapter().deliver_message(subject=getattr(campaign, "subject_" + language), message=message, email=user.email, message_id=f"<campaign-{row.pk}@oweru>")
    except Exception as exc:
        CampaignAttempt.objects.create(delivery=row, success=False, error_type=type(exc).__name__[:100])
        row.status = "FAILED" if row.attempts >= 5 else "WAITING"
        row.next_attempt_at = timezone.now() + timedelta(minutes=2 ** row.attempts)
    else:
        CampaignAttempt.objects.create(delivery=row, success=True)
        row.status, row.sent_at = "SENT", timezone.now()
    row.save()
    return row


@transaction.atomic
def click(token):
    try:
        identifier = signing.loads(token, salt="marketing-click", max_age=30 * 86400)
    except signing.BadSignature:
        raise ValidationError("Invalid or expired campaign link.")
    row = get_object_or_404(CampaignDelivery.objects.select_for_update().select_related("campaign"), pk=identifier, status="SENT")
    if row.clicked_at is None:
        row.clicked_at = timezone.now()
        row.save(update_fields=["clicked_at", "updated_at"])
    return tagged_link(row.campaign.target_path, row.campaign.source_tag)


def results(actor):
    staff(actor, "marketing.send_campaign")
    return list(Campaign.objects.annotate(recipients=Count("deliveries"), sent=Count("deliveries", filter=Q(deliveries__status="SENT")), failed=Count("deliveries", filter=Q(deliveries__status="FAILED")), cancelled=Count("deliveries", filter=Q(deliveries__status="CANCELLED")), clicks=Count("deliveries", filter=Q(deliveries__clicked_at__isnull=False))).values("id", "source_tag", "created_at", "recipients", "sent", "failed", "cancelled", "clicks")[:100])
