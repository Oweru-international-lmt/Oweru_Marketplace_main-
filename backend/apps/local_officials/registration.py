"""SRD 14.2 and LOC-01, LOC-06: inviting, registering, approving and replacing local officials."""
import hashlib
import secrets
from datetime import timedelta
from urllib.parse import quote, urlsplit

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.accounts.managers import normalize_email_address
from apps.accounts.models import User
from apps.audit.services import create_audit_log
from apps.free_checks.services import normalize_phone
from apps.localities.models import Locality
from apps.notifications.services import emit
from apps.payments.documents import save_document
from apps.roles.catalog import ROLE_LOCAL_OFFICIAL
from apps.roles.legacy_authorization.services import _assign, _role
from apps.roles.services import assign_role
from apps.verification.configuration import setting

from .full_check import assign_locality, coverage_manager, revoke_locality
from .models import LocalOfficialInvite, LocalOfficialProfile, generate_official_id
from .services import _profile_for_update, _validate_model

TOKEN_BYTES = 32


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def frontend_url(path):
    base = settings.MARKETPLACE_PUBLIC_URL or ""
    if not base and settings.PASSWORD_RESET_URL:
        parts = urlsplit(settings.PASSWORD_RESET_URL)
        base = f"{parts.scheme}://{parts.netloc}"
    return base.rstrip("/") + path


def send_invite(invite, token, actor):
    """Queue the link for staff delivery by WhatsApp and return it for the screen."""
    link = frontend_url(f"/official/register/{token}")
    day = timezone.localtime(invite.expires_at).strftime("%d/%m/%Y")
    context = {"reference": invite.locality.name, "details": f"{day}.", "link": link}
    rows = emit(event_key=f"official-invite:{invite.pk}:{invite.token_hash[:12]}", purpose="OFFICIAL_REGISTRATION", channels=["outbox"], phone=invite.phone, language="sw", context=context, actor=actor, source=invite, expires_at=invite.expires_at)
    text = rows[0].message if rows else link
    return {"link": link, "message": text, "whatsapp_link": f"https://wa.me/{invite.phone.lstrip('+')}?text={quote(text)}"}


def _new_token():
    for _ in range(8):
        token = secrets.token_urlsafe(TOKEN_BYTES)
        if not LocalOfficialInvite.objects.filter(token_hash=_hash(token)).exists():
            return token
    raise ValidationError("Could not create a registration link.")


def _expiry():
    return timezone.now() + timedelta(days=float(setting("official_registration_days")))


@transaction.atomic
def invite_official(*, actor, locality, phone, replaces=None, request=None):
    actor = coverage_manager(actor)
    area = Locality.objects.select_related("ward__district__region").filter(pk=getattr(locality, "pk", locality), approved=True).first()
    if area is None:
        raise ValidationError({"locality": "An approved street or village is required."})
    try:
        phone = normalize_phone(phone or "")
    except Exception as exc:
        raise ValidationError({"phone": "Use the office WhatsApp number, for example +255712345678."}) from exc
    holder = User.objects.filter(phone=phone).first()
    if holder is not None and not _releasable(holder):
        raise ValidationError({"phone": "This number belongs to another active Oweru account."})
    # One live link per street or village: a new invite replaces any unused one.
    LocalOfficialInvite.objects.filter(locality=area, used_at__isnull=True, cancelled_at__isnull=True).update(cancelled_at=timezone.now())
    token = _new_token()
    invite = LocalOfficialInvite.objects.create(locality=area, phone=phone, token_hash=_hash(token), expires_at=_expiry(), invited_by=actor, replaces=replaces)
    create_audit_log(actor=actor, action="local_official.invited", entity_type="LocalOfficialInvite", entity_id=invite.pk, before={}, after={"locality_id": str(area.pk), "replaces": replaces.official_id if replaces else None}, request=request)
    return invite, token


@transaction.atomic
def resend_invite(*, actor, invite_id, request=None):
    actor = coverage_manager(actor)
    invite = LocalOfficialInvite.objects.select_for_update().select_related("locality").filter(pk=invite_id).first()
    if invite is None:
        raise NotFound("Invite not found.")
    if invite.used_at or invite.cancelled_at:
        raise ValidationError("Only an unused invite can be sent again.")
    token = _new_token()
    invite.token_hash, invite.expires_at = _hash(token), _expiry()
    invite.save(update_fields=["token_hash", "expires_at", "updated_at"])
    create_audit_log(actor=actor, action="local_official.invite_resent", entity_type="LocalOfficialInvite", entity_id=invite.pk, before={}, after={"expires_at": invite.expires_at.isoformat()}, request=request)
    return invite, token


@transaction.atomic
def cancel_invite(*, actor, invite_id, request=None):
    actor = coverage_manager(actor)
    invite = LocalOfficialInvite.objects.select_for_update().filter(pk=invite_id).first()
    if invite is None:
        raise NotFound("Invite not found.")
    if invite.used_at:
        raise ValidationError("A used invite cannot be cancelled.")
    if not invite.cancelled_at:
        invite.cancelled_at = timezone.now()
        invite.save(update_fields=["cancelled_at", "updated_at"])
        create_audit_log(actor=actor, action="local_official.invite_cancelled", entity_type="LocalOfficialInvite", entity_id=invite.pk, before={}, after={}, request=request)
    return invite


def live_invite(token, *, lock=False):
    rows = LocalOfficialInvite.objects.select_related("locality__ward__district__region")
    if lock:
        rows = rows.select_for_update()
    invite = rows.filter(token_hash=_hash(token or "")).first()
    if invite is None or invite.status != "INVITED":
        raise NotFound("This registration link is not valid. Ask Oweru for a new one.")
    return invite


def _releasable(user):
    """A deactivated official's account may hand its office number to the replacement."""
    profile = LocalOfficialProfile.objects.filter(user=user).first()
    return not user.is_active and profile is not None and profile.status == LocalOfficialProfile.Status.DEACTIVATED


def _release_phone(user, request):
    retired = f"{user.phone}~R{secrets.token_hex(4)}"[:30]
    before = user.phone
    User.objects.filter(pk=user.pk).update(phone=retired)
    create_audit_log(actor=None, action="local_official.phone_released", entity_type="User", entity_id=user.pk, before={"phone": before}, after={"phone": retired}, request=request)


@transaction.atomic
def register_official(*, token, full_name, position, national_id_number, email, password, photo, stamp_photo, request=None):
    invite = live_invite(token, lock=True)
    full_name = (full_name or "").strip()
    national_id_number = (national_id_number or "").strip()
    if not full_name or not national_id_number:
        raise ValidationError("Full name and national ID number are required.")
    if position not in LocalOfficialProfile.Position.values:
        raise ValidationError({"position": "Choose Mwenyekiti or Mtendaji."})
    email = normalize_email_address(email or "")
    if User.objects.filter(email=email).exists():
        raise ValidationError({"email": "An account with this email already exists."})
    holder = User.objects.select_for_update().filter(phone=invite.phone).first()
    if holder is not None:
        if not _releasable(holder):
            raise ValidationError({"phone": "This WhatsApp number already has an Oweru account. Ask Oweru for help."})
        _release_phone(holder, request)
    user = User(email=email, phone=invite.phone, full_name=full_name, account_category="operational", is_active=False)
    try:
        validate_password(password, user)
    except DjangoValidationError as exc:
        raise ValidationError({"password": exc.messages}) from exc
    user.set_password(password)
    _validate_model(user)
    user.save()
    profile = LocalOfficialProfile(
        official_id=generate_official_id(), user=user, is_active=False, position=position,
        national_id_number=national_id_number, locality=invite.locality,
        status=LocalOfficialProfile.Status.AWAITING_APPROVAL,
    )
    profile.official_number = profile.official_id
    _validate_model(profile)
    profile.save()
    profile.photo = save_document(actor=user, owner=profile, upload=photo)
    profile.stamp_photo = save_document(actor=user, owner=profile, upload=stamp_photo)
    if profile.photo.mime_type == "application/pdf" or profile.stamp_photo.mime_type == "application/pdf":
        raise ValidationError("The live photo and the stamp must be photos (JPEG or PNG).")
    profile.save(update_fields=["photo", "stamp_photo", "updated_at"])
    invite.used_at, invite.profile = timezone.now(), profile
    invite.save(update_fields=["used_at", "profile", "updated_at"])
    for staff in User.objects.filter(is_active=True, account_category="operational", user_roles__role__code="management", user_roles__is_active=True).distinct():
        emit(event_key=f"official-awaiting:{profile.official_id}:{staff.pk}", purpose="OFFICIAL_AWAITING_APPROVAL", channels=["screen"], recipient=staff, context={"reference": profile.official_id, "details": invite.locality.name, "link": "/staff/partners"}, source=profile)
    create_audit_log(actor=user, action="local_official.registered", entity_type="LocalOfficialProfile", entity_id=profile.pk, before={}, after={"official_id": profile.official_id, "locality_id": str(invite.locality_id), "position": position}, request=request)
    return profile


@transaction.atomic
def approve_official(*, actor, official_id, request=None):
    actor = coverage_manager(actor)
    profile = _profile_for_update(LocalOfficialProfile.objects.filter(official_id=official_id).values_list("pk", flat=True).first())
    if profile.status != LocalOfficialProfile.Status.AWAITING_APPROVAL:
        raise ValidationError("Only an official awaiting approval can be approved.")
    user = User.objects.select_for_update().get(pk=profile.user_id)
    user.is_active = True
    user.save(update_fields=["is_active"])
    assign_role(user=user, role_code=ROLE_LOCAL_OFFICIAL, assigned_by=actor, request=request)
    _assign(user, _role(ROLE_LOCAL_OFFICIAL), actor, request)
    profile.status, profile.is_active = LocalOfficialProfile.Status.ACTIVE, True
    profile.confirmed_by, profile.confirmed_at = actor, timezone.now()
    profile.save(update_fields=["status", "is_active", "confirmed_by", "confirmed_at", "updated_at"])
    create_audit_log(actor=actor, action="local_official.approved", entity_type="LocalOfficialProfile", entity_id=profile.pk, before={"status": "AWAITING_APPROVAL"}, after={"status": "ACTIVE"}, request=request)
    if profile.locality_id:
        # Waiting tasks for this street or village move into the new official's dashboard.
        assign_locality(actor=actor, official=profile, locality=profile.locality_id, request=request)
    emit(event_key=f"official-approved:{profile.official_id}", purpose="OFFICIAL_APPROVED", channels=["outbox", "email"], recipient=user, context={"reference": profile.official_id, "link": frontend_url("/login")}, actor=actor, source=profile)
    return profile


@transaction.atomic
def deactivate_official(*, actor, official_id, reason, request=None):
    actor = coverage_manager(actor)
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError({"reason": "Give the reason for switching the official off."})
    profile = _profile_for_update(LocalOfficialProfile.objects.filter(official_id=official_id).values_list("pk", flat=True).first())
    if profile.status == LocalOfficialProfile.Status.DEACTIVATED:
        return profile
    before = profile.status
    profile.status, profile.is_active, profile.deactivated_reason = LocalOfficialProfile.Status.DEACTIVATED, False, reason[:1000]
    profile.save(update_fields=["status", "is_active", "deactivated_reason", "updated_at"])
    User.objects.filter(pk=profile.user_id).update(is_active=False)
    # LOC-06: no further tasks; open tasks go to the street's other officials or back to Needs official.
    for row in profile.locality_coverage.filter(revoked_at__isnull=True):
        revoke_locality(actor=actor, coverage=row, request=request)
    create_audit_log(actor=actor, action="local_official.deactivated", entity_type="LocalOfficialProfile", entity_id=profile.pk, before={"status": before}, after={"status": "DEACTIVATED", "reason": reason[:1000]}, request=request)
    return profile
