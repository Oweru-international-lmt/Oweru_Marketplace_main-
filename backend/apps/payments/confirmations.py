import hashlib
import secrets
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.accounts.models import User
from apps.listings.models import Listing
from apps.leads.policies import authorize, management
from apps.leads.services import audit
from apps.deals.services import lock_deal, require_deal
from .models import ConfirmationDelivery, OwnerContact, BankAccount, PhoneConfirmation
from .idempotency import execute
from .services import record_receipt


@transaction.atomic
def request_confirmation(*, actor, purpose, listing_id=None, deal_id=None, owner_name="", owner_whatsapp="", request=None):
    actor = authorize(actor, "listing.update" if purpose in {"OWNER_PRICE", "PHONE"} else "deal.update")
    listing, deal, user = None, None, None
    if purpose == "PHONE":
        user = User.objects.select_for_update().get(pk=actor.pk)
        recipient, context = user.phone, {"phone": user.phone}
    elif purpose == "OWNER_PRICE":
        listing = Listing.objects.select_for_update().get(listing_id=listing_id)
        if listing.lister_id != actor.pk or listing.lister_kind != "AGENT" or listing.status not in {"DRAFT", "ACTIVE"}:
            raise PermissionDenied("Only the relevant Agent may request owner confirmation.")
        if not listing.rate_table_id or not owner_name.strip() or not owner_whatsapp.strip() or owner_whatsapp.strip() == actor.phone:
            raise ValidationError("Frozen rate version and distinct owner name/WhatsApp are required.")
        contact, _ = OwnerContact.objects.get_or_create(listing=listing, defaults={"name": owner_name.strip(), "whatsapp": owner_whatsapp.strip()})
        if contact.confirmed_at and (contact.name != owner_name.strip() or contact.whatsapp != owner_whatsapp.strip()):
            raise ValidationError("A confirmed owner contact cannot be replaced through this workflow.")
        contact.name, contact.whatsapp = owner_name.strip(), owner_whatsapp.strip()
        contact.save()
        recipient = contact.whatsapp
        context = {"listing_id": listing.listing_id, "property_id": listing.property.property_id, "owner_price": str(listing.owner_price), "total_rate": str(listing.rate_table.total_rate), "rate_table_id": str(listing.rate_table_id), "owner_receives_unrounded": str(listing.owner_price * (1 - listing.rate_table.total_rate))}
        if OwnerContact.objects.filter(whatsapp=recipient).exclude(listing__lister=actor).exists():
            audit(actor, "owner_contact.shared_number_flagged", contact, after={"reason": "used_by_multiple_agents"}, request=request)
    elif purpose == "OWNER_RECEIPT":
        deal = lock_deal(deal_id)
        require_deal(actor, deal, "deal.update", lister=True)
        if deal.lister_kind != "AGENT" or deal.state != "OPEN":
            raise ValidationError("External owner receipt links are for active agent Deals.")
        contact = OwnerContact.objects.get(listing=deal.listing)
        recipient = contact.whatsapp
        context = {"deal_id": str(deal.pk), "amount": str(deal.buyer_to_owner), "final_selling_price": str(deal.final_selling_price)}
    else:
        raise ValidationError("Unsupported confirmation purpose.")
    # Supersede earlier links for the same context; sent links remain single-use.
    pending = ConfirmationDelivery.objects.filter(purpose=purpose, listing=listing, deal=deal, user=user, consumed_at__isnull=True)
    pending.update(consumed_at=timezone.now(), delivery_token="")
    token = secrets.token_urlsafe(32)
    delivery = ConfirmationDelivery.objects.create(purpose=purpose, listing=listing, deal=deal, user=user, recipient=recipient, context=context, token_digest=hashlib.sha256(token.encode()).hexdigest(), delivery_token=token, expires_at=timezone.now() + timedelta(days=settings.OWNER_CONFIRMATION_DAYS))
    audit(actor, "confirmation.queued", delivery, after={"purpose": purpose}, request=request)
    # Bearer token intentionally excluded from Agent/initiator response.
    return {"delivery_id": str(delivery.pk), "status": "QUEUED"}


@transaction.atomic
def mark_sent(*, actor, delivery_id, request=None):
    actor = authorize(actor, "outbox.send")
    if not management(actor):
        raise PermissionDenied("Owner confirmations must be sent by authorized Oweru staff.")
    delivery = ConfirmationDelivery.objects.select_for_update().get(pk=delivery_id)
    if delivery.consumed_at or delivery.expires_at <= timezone.now():
        raise ValidationError("This confirmation link is no longer usable.")
    if not delivery.sent_at:
        delivery.sent_at, delivery.sent_by = timezone.now(), actor
        delivery.save(update_fields=["sent_at", "sent_by", "updated_at"])
        audit(actor, "confirmation.sent", delivery, after={"purpose": delivery.purpose}, request=request)
    return {"delivery_id": str(delivery.pk), "sent_at": delivery.sent_at.isoformat()}


def check_token(delivery, token, *, allow_consumed=False):
    if not isinstance(token, str) or not secrets.compare_digest(delivery.token_digest, hashlib.sha256(token.encode()).hexdigest()) or not delivery.sent_at or delivery.expires_at <= timezone.now() or (delivery.consumed_at and not allow_consumed):
        raise PermissionDenied("Invalid, unsent, expired or consumed confirmation link.")


def decide(*, delivery_id, token, decision, key, bank=None, bank_reference="", request=None):
    if decision not in {"CONFIRM", "DECLINE"}:
        raise ValidationError("Confirm or Decline is required.")
    delivery = ConfirmationDelivery.objects.get(pk=delivery_id)
    resource = delivery.deal_id or delivery.listing_id or delivery.user_id
    def lock():
        if delivery.deal_id:
            lock_deal(delivery.deal_id)
        elif delivery.listing_id:
            Listing.objects.select_for_update().get(pk=delivery.listing_id)
        else:
            User.objects.select_for_update().get(pk=delivery.user_id)
        return ConfirmationDelivery.objects.select_for_update().get(pk=delivery_id)
    def policy(row):
        check_token(row, token, allow_consumed=True)
    def mutate(row):
        check_token(row, token)
        now = timezone.now()
        if row.purpose == "PHONE":
            user = User.objects.get(pk=row.user_id, is_active=True)
            if user.phone != row.recipient:
                raise ValidationError("Account phone has changed; request a new confirmation.")
            if decision == "CONFIRM":
                PhoneConfirmation.objects.update_or_create(user=user, defaults={"phone": row.recipient, "confirmed_at": now})
        elif row.purpose == "OWNER_PRICE":
            listing = Listing.objects.get(pk=row.listing_id)
            contact = OwnerContact.objects.select_for_update().get(listing=listing)
            if str(listing.owner_price) != row.context["owner_price"] or str(listing.rate_table_id) != row.context["rate_table_id"] or row.recipient != contact.whatsapp:
                raise ValidationError("Listing confirmation context changed; request a new link.")
            if decision == "CONFIRM":
                if bank is None:
                    raise ValidationError("Owner receiving bank account is required.")
                BankAccount.objects.update_or_create(owner_contact=contact, defaults=bank)
                contact.confirmed_at, contact.confirmed_owner_price = now, listing.owner_price
            else:
                listing.status = "SUSPENDED"
                listing.save(update_fields=["status", "updated_at"])
                audit(None, "listing.suspended", listing, after={"reason": "owner_declined"}, request=request)
            contact.decision = decision
            contact.save()
        elif row.purpose == "OWNER_RECEIPT":
            deal = lock_deal(row.deal_id)
            if str(deal.buyer_to_owner) != row.context["amount"] or deal.state != "OPEN":
                raise ValidationError("Receipt confirmation context changed.")
            if decision == "CONFIRM":
                if not bank_reference.strip():
                    raise ValidationError("Receipt bank reference is required.")
                record_receipt(deal=deal, actor=None, transfer="OWNER", bank_reference=bank_reference, delivery=row, request=request)
        row.consumed_at, row.decision, row.delivery_token = now, decision, ""
        if request:
            row.ip_address = request.META.get("REMOTE_ADDR") or None
            row.user_agent = request.META.get("HTTP_USER_AGENT", "")[:2000]
        row.save()
        audit(None, "confirmation.decided", row, after={"purpose": row.purpose, "decision": decision}, request=request)
        return {"delivery_id": str(row.pk), "decision": decision}
    return execute(actor_scope=f"delivery:{delivery_id}", operation="confirmation.decision", resource=resource, key=key, payload={"decision": decision, "bank": bank, "bank_reference": bank_reference.strip()}, lock=lock, authorize=policy, mutation=mutate)
