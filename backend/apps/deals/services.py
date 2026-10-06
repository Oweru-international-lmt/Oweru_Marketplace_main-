from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.listings.models import Listing
from apps.leads.models import Lead
from apps.leads.policies import authorize, management, require_lister
from apps.leads.services import audit, record_transition, review_lost_sales
from apps.commissions.services import CommissionService
from .models import Deal


def lock_deal(deal_id):
    # All finance writes serialize on this same stable row.
    return Deal.objects.select_for_update(of=("self",)).select_related("listing", "lead", "rate_table").get(pk=deal_id)


def require_deal(actor, deal, permission="deal.view", buyer=False, lister=False, manager=False):
    actor = authorize(actor, permission)
    allowed = (buyer and deal.buyer_id == actor.pk) or (lister and deal.lister_id == actor.pk) or (manager and management(actor))
    if not allowed:
        raise PermissionDenied("You do not have access to this Deal action.")
    return actor


class DealClosingService:
    @staticmethod
    @transaction.atomic
    def close(*, actor, lead_id, final_selling_price, request=None):
        listing_id = Lead.objects.only("listing_id").get(pk=lead_id).listing_id
        listing = Listing.objects.select_for_update(of=("self",)).select_related("rate_table", "lister").get(pk=listing_id)
        lead = Lead.objects.select_for_update().get(pk=lead_id)
        actor = require_lister(actor, lead)
        authorize(actor, "deal.update")
        existing = Deal.objects.filter(lead=lead).first()
        if existing:
            if existing.state == "CANCELLED":
                raise ValidationError("A cancelled Deal cannot be reopened through Closing.")
            from apps.commissions.services import money
            if final_selling_price is None or money(final_selling_price) != existing.final_selling_price:
                raise ValidationError("Closing already exists with a different final price.")
            return existing
        if lead.stage != "NEGOTIATION" or listing.status != "ACTIVE":
            raise ValidationError("Closing requires a Negotiation Lead and an active Listing.")
        if lead.lister_id != listing.lister_id or lead.property_id != listing.property_id or not lead.buyer_id:
            raise ValidationError("Lead participants and property must match the Listing.")
        if not lead.buyer.is_active or not listing.lister.is_active:
            raise ValidationError("Deal participants must be active.")
        if not listing.rate_table_id:
            raise ValidationError("This Listing has no historical frozen rate version; it cannot close.")
        if listing.lister_kind == "AGENT":
            from apps.payments.models import OwnerContact
            owner = OwnerContact.objects.select_for_update().filter(listing=listing).first()
            if not owner or owner.decision != "CONFIRM" or not owner.confirmed_at or owner.confirmed_owner_price != listing.owner_price:
                raise ValidationError("Owner confirmation of the current owner price is required.")
        breakdown = CommissionService.calculate(owner_price=listing.owner_price, selling_price=final_selling_price, rate_table=listing.rate_table, lister_kind=listing.lister_kind)
        from apps.payments.models import BankAccount
        from apps.payments.services import bank_data
        owner_bank = BankAccount.objects.filter(user_id=listing.lister_id).first() if listing.lister_kind == "OWNER" else BankAccount.objects.filter(owner_contact__listing=listing).first()
        oweru_bank = BankAccount.objects.filter(is_oweru=True).first()
        if owner_bank is None or oweru_bank is None:
            raise ValidationError("Owner and Oweru receiving bank accounts are required before Closing.")
        deal = Deal.objects.create(lead=lead, listing=listing, property=listing.property, buyer=lead.buyer, lister=lead.lister, buyer_name=lead.buyer_name, buyer_whatsapp=lead.buyer_whatsapp, lister_kind=listing.lister_kind, rate_table=listing.rate_table, owner_bank_snapshot=bank_data(owner_bank), oweru_bank_snapshot=bank_data(oweru_bank), **breakdown)
        record_transition(lead, "CLOSING", actor, request=request)
        listing.status = "UNDER_OFFER"
        listing.save(update_fields=["status", "updated_at"])
        audit(actor, "listing.under_offer", listing, before={"status": "ACTIVE"}, after={"status": "UNDER_OFFER"}, request=request)
        audit(actor, "deal.created", deal, after={"lead_id": str(lead.pk)}, request=request)
        audit(actor, "deal.final_price_recorded", deal, after={"price": str(deal.final_selling_price)}, request=request)
        audit(actor, "commission.calculated", deal, after={k: str(v) for k, v in breakdown.items() if k != "rate_band"}, request=request)
        from apps.payments.notices import queue_notice
        queue_notice(recipient=deal.buyer, purpose="PAYMENT_INSTRUCTIONS", deal=deal)
        queue_notice(recipient=deal.buyer, purpose="FULL_CHECK_OFFER", deal=deal)
        return deal


@transaction.atomic
def reprice(*, actor, deal_id, final_selling_price, request=None):
    deal = lock_deal(deal_id)
    actor = require_deal(actor, deal, "deal.update", lister=True)
    if deal.state != "OPEN" or deal.payment_proofs.exists() or deal.payment_confirmations.exists() or hasattr(deal, "tax_receipt") or deal.agreement_id:
        raise ValidationError("Financial activity or agreement submission makes this breakdown immutable.")
    from apps.commissions.services import money
    final_selling_price = money(final_selling_price)
    if deal.final_selling_price == final_selling_price:
        return deal
    before = str(deal.final_selling_price)
    values = CommissionService.calculate(owner_price=deal.owner_price, selling_price=final_selling_price, rate_table=deal.rate_table, lister_kind=deal.lister_kind)
    for key, value in values.items():
        setattr(deal, key, value)
    deal.save()
    audit(actor, "commission.recalculated", deal, before={"price": before}, after={"price": str(final_selling_price)}, request=request)
    return deal


@transaction.atomic
def complete_deal(*, actor, deal_id, request=None):
    deal = lock_deal(deal_id)
    actor = require_deal(actor, deal, "payment.confirm", manager=True)
    if deal.state == "COMPLETE":
        return deal
    confirmations = set(deal.payment_confirmations.values_list("transfer", flat=True))
    if confirmations != {"OWNER", "OWERU"} or not deal.agreement_id or not deal.agreement_price_confirmed_at or not deal.agreement_approved_at:
        raise ValidationError("Both receipts and the confirmed, approved signed agreement are required.")
    listing = Listing.objects.select_for_update().get(pk=deal.listing_id)
    lead = Lead.objects.select_for_update().get(pk=deal.lead_id)
    if listing.status != "UNDER_OFFER" or lead.stage != "CLOSING":
        raise ValidationError("The Listing and Lead are not ready for completion.")
    deal.state, deal.completed_at = "COMPLETE", timezone.now()
    deal.save(update_fields=["state", "completed_at", "updated_at"])
    record_transition(lead, "WON", actor, request=request)
    listing.status = "SOLD"
    listing.save(update_fields=["status", "updated_at"])
    audit(actor, "deal.completed", deal, after={"state": "COMPLETE"}, request=request)
    audit(actor, "listing.sold", listing, after={"status": "SOLD"}, request=request)
    if deal.lister_kind == "AGENT":
        from apps.payments.services import create_payout
        create_payout(deal=deal, actor=actor, request=request)
    review_lost_sales(deal)
    return deal


@transaction.atomic
def lose_unpaid_deal(*, actor, lead_id, reason, request=None):
    deal = Deal.objects.get(lead_id=lead_id)
    deal = lock_deal(deal.pk)
    listing = Listing.objects.select_for_update().get(pk=deal.listing_id)
    lead = Lead.objects.select_for_update().get(pk=lead_id)
    actor = require_lister(actor, lead)
    authorize(actor, "deal.update")
    if not reason.strip():
        raise ValidationError("A Lost reason is required.")
    if deal.state != "OPEN" or deal.payment_proofs.exists() or deal.payment_confirmations.exists() or deal.agreement_id:
        raise ValidationError("A Deal with financial/agreement activity requires Management review before cancellation; this Lead action cannot reverse it.")
    deal.state = "CANCELLED"
    deal.save(update_fields=["state", "updated_at"])
    record_transition(lead, "LOST", actor, reason, request)
    listing.status = "ACTIVE"
    listing.save(update_fields=["status", "updated_at"])
    audit(actor, "deal.cancelled", deal, after={"reason": reason}, request=request)
    audit(actor, "listing.offer_released", listing, before={"status": "UNDER_OFFER"}, after={"status": "ACTIVE"}, request=request)
    return lead
