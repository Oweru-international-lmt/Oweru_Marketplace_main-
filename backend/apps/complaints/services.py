from datetime import timedelta
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.crypto import salted_hmac
from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.accounts.models import User
from apps.audit.services import create_audit_log
from apps.leads.policies import authorize, management
from apps.payments.documents import save_document
from apps.payments.idempotency import Conflict
from apps.payments.models import Payout, PayoutBlock
from apps.payments.services import working_deadline
from apps.deals.services import lock_deal
from apps.properties.models import PropertyRecord
from apps.verification.configuration import setting
from apps.verification.models import VerificationJob
from apps.verification.task_services import private_write_scope
from .models import Complaint, ComplaintHistory, ComplaintResponse, ComplaintEvidence, ComplaintNotice

EDGES = {"RECEIVED": {"IN_REVIEW"}, "IN_REVIEW": {"WAITING_INFORMATION", "RESOLVED"}, "WAITING_INFORMATION": {"IN_REVIEW", "RESOLVED"}, "RESOLVED": {"CLOSED"}, "UNDER_FINAL_REVIEW": {"CLOSED"}, "CLOSED": set()}


def token_for(row):
    return salted_hmac("oweru.complaint-status", str(row.pk)).hexdigest()


def public_access(complaint_id, token):
    import secrets
    row = get_object_or_404(Complaint, pk=complaint_id)
    if not isinstance(token, str) or not secrets.compare_digest(token_for(row), token):
        raise PermissionDenied("Invalid complaint status link.")
    return row


def require_handler(actor, row):
    actor = authorize(actor, "complaint.handle")
    if row.status == "UNDER_FINAL_REVIEW":
        if not management(actor) or actor.management_position != "DIRECTOR":
            raise PermissionDenied("Director final review is required.")
    elif management(actor):
        if row.route == "HEAD_OPERATIONS" and actor.management_position not in {"HEAD_OPERATIONS", "DIRECTOR"}:
            raise PermissionDenied("Head of Operations routing is required.")
    elif not actor.has_role("verifier") or row.category != "VERIFICATION" or row.route != "VERIFIER" or row.handler_id != actor.pk:
        raise PermissionDenied("Only the assigned verification complaint handler has access.")
    return actor


def lock_complaint(complaint_id):
    deal_id = get_object_or_404(Complaint.objects.only("deal_id"), pk=complaint_id).deal_id
    if deal_id:
        lock_deal(deal_id)
    return get_object_or_404(Complaint.objects.select_for_update(), pk=complaint_id)


def sync_payout(row, actor=None, request=None):
    # Called only after intake validation, under Deal -> Complaint ordered locks.
    if row.deal_id is None:
        return
    opened = row.status not in {"RESOLVED", "CLOSED"}
    block, _ = PayoutBlock.objects.get_or_create(deal_id=row.deal_id, external_reference=row.reference)
    if block.is_open != opened:
        block.is_open = opened
        block.save(update_fields=["is_open", "updated_at"])
    payout = Payout.objects.select_for_update().filter(deal_id=row.deal_id).first()
    if payout and opened and payout.status not in {"PAID", "ON_HOLD"}:
        previous = payout.status
        payout.status = "ON_HOLD"
        payout.hold_reason = "Open complaint " + row.reference
        payout.save(update_fields=["status", "hold_reason", "updated_at"])
        create_audit_log(actor=actor, action="payout.held", entity_type="Payout", entity_id=payout.pk, before={"status": previous}, after={"source": "complaint", "status": "ON_HOLD"}, request=request)


def changed(row, actor, reason, request=None):
    ComplaintHistory.objects.create(complaint=row, actor=actor, status=row.status, reason=reason, version=row.version)
    ComplaintNotice.objects.get_or_create(complaint=row, purpose="COMPLAINT_UPDATE", version=row.version, defaults={"channels": ["outbox"] + (["email"] if row.email else [])})
    sync_payout(row, actor, request)
    create_audit_log(actor=actor, action="complaint.transitioned", entity_type="Complaint", entity_id=row.pk, after={"status": row.status, "version": row.version}, request=request)


def lodge(*, values, source="WEB", actor=None, evidence=(), request=None):
    from .api import Intake
    serializer = Intake(data=values)
    serializer.is_valid(raise_exception=True)
    data = dict(serializer.validated_data)
    from apps.free_checks.services import normalize_phone
    data["phone"] = normalize_phone(data["phone"])
    if source not in {"WEB", "EMAIL", "WHATSAPP"}:
        raise ValidationError("Invalid complaint source.")
    if source != "WEB":
        actor = authorize(actor, "account.view")
        if actor.account_category != "operational" or not any(actor.has_role(role) for role in ["management", "verifier", "marketer"]):
            raise PermissionDenied()
        if source == "EMAIL" and not data.get("email"):
            raise ValidationError("Email intake requires an acknowledgement address.")
    else:
        actor = None
    if len(evidence) > 5:
        raise ValidationError("At most five evidence files are allowed.")
    with private_write_scope(), transaction.atomic():
        prop = get_object_or_404(PropertyRecord, property_id=data.pop("property_reference")) if data.get("property_reference") else None
        data.pop("property_reference", None)
        if data.get("deal_id"):
            from apps.deals.models import Deal
            get_object_or_404(Deal.objects.only("id"), pk=data["deal_id"])
        deal = lock_deal(data.pop("deal_id")) if data.get("deal_id") else None
        data.pop("deal_id", None)
        if deal:
            if prop and prop.pk != deal.property_id:
                raise ValidationError("Complaint property and deal must match.")
            prop = deal.property
        category = data["category"]
        route = "HEAD_OPERATIONS" if category in {"FAKE_LISTING", "WRONG_LISTING", "OTHER"} else "VERIFIER" if category == "VERIFICATION" else "MANAGEMENT"
        handler = User.objects.filter(is_active=True, management_position="HEAD_OPERATIONS").first() if route == "HEAD_OPERATIONS" else None
        if route == "VERIFIER" and prop:
            job = VerificationJob.objects.filter(property=prop, verifier__is_active=True).order_by("-created_at").first()
            handler = job.verifier if job else None
        now = timezone.now()
        days = int(setting("complaint_payment_working_days" if category in {"PAYMENT", "PAYOUT"} else "complaint_other_working_days"))
        row = Complaint.objects.create(**data, source=source, property=prop, deal=deal, route=route, handler=handler, created_by=actor, acknowledgement_due_at=working_deadline(now, int(setting("complaint_ack_working_days"))), resolution_due_at=working_deadline(now, days))
        ComplaintHistory.objects.create(complaint=row, actor=actor, status=row.status, reason="Complaint received", version=1)
        channels = ["screen"] + (["outbox"] if source == "WHATSAPP" else ["email"] if source == "EMAIL" else [])
        ComplaintNotice.objects.create(complaint=row, purpose="COMPLAINT_NUMBER", version=1, channels=channels)
        for upload in evidence:
            ComplaintEvidence.objects.create(complaint=row, media=save_document(actor=actor, owner=row, upload=upload))
        sync_payout(row, actor, request)
        create_audit_log(actor=actor, action="complaint.received", entity_type="Complaint", entity_id=row.pk, after={"source": source, "category": category}, request=request)
        return row


@transaction.atomic
def transition(*, actor, complaint_id, status, version, reason, outcome="", request=None):
    row = lock_complaint(complaint_id)
    actor = require_handler(actor, row)
    if row.version != version:
        raise Conflict("Complaint changed; refresh before acting.")
    if status not in EDGES[row.status] or not reason.strip():
        raise ValidationError("A valid state transition and reason are required.")
    if status == "RESOLVED" or row.status == "UNDER_FINAL_REVIEW":
        if not outcome.strip():
            raise ValidationError("Outcome and reasons are required.")
        row.outcome, row.reasons = outcome.strip(), reason.strip()
        row.resolved_at = timezone.now()
    row.status, row.version = status, row.version + 1
    row.save()
    changed(row, actor, reason, request)
    return row


@transaction.atomic
def request_final_review(*, complaint_id, token, reason, request=None):
    public_access(complaint_id, token)
    row = lock_complaint(complaint_id)
    if row.status not in {"RESOLVED", "CLOSED"} or row.final_review_requested_at or row.resolved_at is None or timezone.now() > row.resolved_at + timedelta(days=float(setting("complaint_final_review_days"))) or not reason.strip():
        raise ValidationError("Final review requires a resolved complaint within the request window and a reason.")
    row.status, row.route = "UNDER_FINAL_REVIEW", "DIRECTOR"
    row.final_review_requested_at, row.version = timezone.now(), row.version + 1
    row.handler = User.objects.filter(is_active=True, management_position="DIRECTOR").first()
    row.save()
    changed(row, None, reason, request)
    return row


@transaction.atomic
def assign(*, actor, complaint_id, handler, version, escalate=False, request=None):
    row = lock_complaint(complaint_id)
    actor = require_handler(actor, row)
    if not management(actor) and not (escalate and row.category == "VERIFICATION" and row.handler_id == actor.pk):
        raise PermissionDenied("Management assignment is required.")
    if row.status in {"CLOSED", "RESOLVED", "UNDER_FINAL_REVIEW"} or row.version != version:
        raise Conflict("Complaint cannot be assigned in its current version/state.")
    target = authorize(handler, "complaint.handle")
    if escalate:
        if row.category != "VERIFICATION" or not management(target):
            raise ValidationError("Verification complaints escalate to Management.")
        row.route = "MANAGEMENT"
    elif row.route == "VERIFIER":
        if not target.has_role("verifier"):
            raise ValidationError("A Verifier is required.")
    elif not management(target) or row.route == "HEAD_OPERATIONS" and target.management_position != "HEAD_OPERATIONS":
        raise PermissionDenied("Handler must match the complaint route.")
    row.handler, row.version = target, row.version + 1
    row.save()
    changed(row, actor, "Escalated to Management" if escalate else "Handler assigned", request)
    return row


def add_response(*, complaint_id, text, actor=None, token=None, evidence=(), request=None):
    if not isinstance(text, str) or not text.strip() or len(text) > 10000 or len(evidence) > 5:
        raise ValidationError("A bounded response and at most five files are required.")
    with private_write_scope(), transaction.atomic():
        row = lock_complaint(complaint_id)
        if token is not None:
            public_access(complaint_id, token)
            actor = None
        else:
            actor = require_handler(actor, row)
        if row.status in {"RESOLVED", "CLOSED"}:
            raise ValidationError("Responses are accepted only while the complaint is under review.")
        response = ComplaintResponse.objects.create(complaint=row, actor=actor, text=text.strip(), from_complainant=actor is None)
        for upload in evidence:
            ComplaintEvidence.objects.create(complaint=row, media=save_document(actor=actor, owner=row, upload=upload))
        create_audit_log(actor=actor, action="complaint.response_added", entity_type="ComplaintResponse", entity_id=response.pk, request=request)
        return response
