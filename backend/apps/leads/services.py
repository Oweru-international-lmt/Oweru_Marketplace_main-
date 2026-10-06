from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.audit.services import create_audit_log
from apps.listings.models import Listing
from apps.lister_identity.services import add_calendar_months
from .models import Lead, LeadNote, LeadTransition, LostLeadReview
from .policies import authorize, require_lister


def audit(actor, action, obj, before=None, after=None, request=None):
    return create_audit_log(actor=actor, action=action, entity_type=type(obj).__name__, entity_id=obj.pk, before=before or {}, after=after or {}, request=request)


@transaction.atomic
def create_lead(*, actor, listing_id, source, buyer_name=None, buyer_whatsapp=None, request=None):
    actor = authorize(actor, "lead.create")
    listing = Listing.objects.select_for_update().get(listing_id=listing_id)
    if listing.status != Listing.Status.ACTIVE:
        raise ValidationError("Interest requires an active listing.")
    if source not in Lead.Source.values:
        raise ValidationError({"source": "Unsupported interest source."})
    buyer = actor
    if listing.lister_id == actor.pk:
        authorize(actor, "lead.update")
        if not buyer_name or not buyer_whatsapp or buyer_whatsapp == actor.phone:
            raise ValidationError("An external customer's name and distinct WhatsApp are required.")
        from apps.accounts.models import User
        buyer = User.objects.filter(phone=buyer_whatsapp, account_category="public", is_active=True).first()
    elif buyer_name is not None or buyer_whatsapp is not None:
        raise ValidationError("Buyers cannot override their account contact snapshot.")
    lead = Lead.objects.create(listing=listing, property=listing.property, lister=listing.lister, buyer=buyer, buyer_name=buyer.full_name if buyer else buyer_name.strip(), buyer_whatsapp=buyer.phone if buyer else buyer_whatsapp.strip(), source=source)
    audit(actor, "lead.created", lead, after={"source": source, "stage": lead.stage}, request=request)
    from apps.payments.notices import queue_notice
    queue_notice(recipient=listing.lister, purpose="LEAD_CREATED", lead=lead)
    return lead


def record_transition(lead, stage, actor, reason="", request=None):
    previous = lead.stage
    lead.stage = stage
    if stage == Lead.Stage.LOST:
        lead.lost_at = timezone.now()
    lead.save(update_fields=["stage", "lost_at", "updated_at"])
    LeadTransition.objects.create(lead=lead, from_stage=previous, to_stage=stage, actor=actor, reason=reason)
    audit(actor, "lead.lost" if stage == Lead.Stage.LOST else "lead.transitioned", lead, before={"stage": previous}, after={"stage": stage, "reason": reason}, request=request)


class LeadTransitionService:
    NEXT = {"NEW": "CONTACTED", "CONTACTED": "VIEWING", "VIEWING": "NEGOTIATION", "NEGOTIATION": "CLOSING"}

    @staticmethod
    @transaction.atomic
    def transition(*, actor, lead_id, stage, reason="", final_selling_price=None, request=None):
        # Closing locks listing before lead, consistently with completion.
        if stage == Lead.Stage.CLOSING:
            from apps.deals.services import DealClosingService
            return DealClosingService.close(actor=actor, lead_id=lead_id, final_selling_price=final_selling_price, request=request).lead
        if stage == Lead.Stage.LOST and Lead.objects.filter(pk=lead_id, stage="CLOSING").exists():
            from apps.deals.services import lose_unpaid_deal
            return lose_unpaid_deal(actor=actor, lead_id=lead_id, reason=reason, request=request)
        lead = Lead.objects.select_for_update().get(pk=lead_id)
        actor = require_lister(actor, lead)
        if stage in {Lead.Stage.WON, Lead.Stage.CLOSING} or lead.stage in {Lead.Stage.WON, Lead.Stage.LOST}:
            raise ValidationError("This transition is not allowed.")
        if stage == Lead.Stage.LOST:
            if not reason.strip():
                raise ValidationError({"reason": "A Lost reason is required."})
            if lead.stage == Lead.Stage.CLOSING:
                raise ValidationError("An open Deal must be resolved before marking its Lead Lost.")
        elif LeadTransitionService.NEXT.get(lead.stage) != stage:
            raise ValidationError("Lead stages must advance in order.")
        record_transition(lead, stage, actor, reason, request)
        return lead


@transaction.atomic
def add_note(*, actor, lead_id, text, request=None):
    lead = Lead.objects.select_for_update().get(pk=lead_id)
    actor = require_lister(actor, lead)
    if not text.strip():
        raise ValidationError({"text": "A note is required."})
    note = LeadNote.objects.create(lead=lead, actor=actor, text=text.strip())
    audit(actor, "lead.note_added", lead, after={"note_id": str(note.pk)}, request=request)
    return note


@transaction.atomic
def set_follow_up(*, actor, lead_id, follow_up_at, request=None):
    lead = Lead.objects.select_for_update().get(pk=lead_id)
    actor = require_lister(actor, lead)
    before = lead.follow_up_at.isoformat() if lead.follow_up_at else None
    lead.follow_up_at = follow_up_at
    lead.save(update_fields=["follow_up_at", "updated_at"])
    audit(actor, "lead.follow_up_changed", lead, before={"follow_up_at": before}, after={"follow_up_at": follow_up_at.isoformat() if follow_up_at else None}, request=request)
    return lead


@transaction.atomic
def review_lost_sales(deal):
    if deal.state != "COMPLETE":
        return 0
    earliest = add_calendar_months(deal.completed_at, -settings.LEAD_LOST_REVIEW_MONTHS)
    matches = Lead.objects.filter(property_id=deal.property_id, stage="LOST", lost_at__gte=earliest, lost_at__lte=deal.completed_at)
    if deal.buyer_id:
        matches = matches.filter(buyer_id=deal.buyer_id)
    else:
        matches = matches.filter(buyer_whatsapp=deal.buyer_whatsapp)
    count = 0
    for lead in matches:
        review, created = LostLeadReview.objects.get_or_create(lost_lead=lead, sold_deal=deal)
        if created:
            audit(None, "lead.lost_sale_flagged", review, after={"lead_id": str(lead.pk), "deal_id": str(deal.pk)})
            count += 1
    return count
