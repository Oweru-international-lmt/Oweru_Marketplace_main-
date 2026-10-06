from datetime import timedelta, date
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.leads.policies import authorize, management
from apps.leads.services import audit
from apps.deals.services import lock_deal, require_deal, complete_deal
from .models import BankAccount, PaymentProof, PaymentConfirmation, OfficialTaxReceipt, Payout, PayoutBlock
from .documents import validate_document, save_document
from .idempotency import execute, Conflict


def payment_status(deal):
    if deal.state == "COMPLETE":
        return "COMPLETE"
    confirmed = set(deal.payment_confirmations.values_list("transfer", flat=True))
    if confirmed == {"OWNER", "OWERU"}:
        return "BOTH_CONFIRMED"
    if "OWERU" in confirmed:
        return "OWERU_CONFIRMED"
    if "OWNER" in confirmed:
        return "OWNER_CONFIRMED"
    return "PROOF_UPLOADED" if deal.payment_proofs.exists() else "AWAITING_PAYMENT"


def bank_data(bank):
    return {field: getattr(bank, field) for field in ["bank_name", "account_name", "account_number", "branch"]}


@transaction.atomic
def instructions(*, actor, deal_id, request=None):
    deal = lock_deal(deal_id)
    actor = require_deal(actor, deal, "payment.submit_proof", buyer=True)
    if deal.state != "OPEN":
        raise ValidationError("Bank instructions are available only for an active Deal.")
    if not deal.owner_bank_snapshot or not deal.oweru_bank_snapshot:
        raise ValidationError("The receiving bank accounts are not configured.")
    audit(actor, "sensitive_data.accessed", deal, after={"purpose": "payment_instructions"}, request=request)
    return {"deal_id": str(deal.pk), "owner": {"amount": str(deal.buyer_to_owner), "bank": deal.owner_bank_snapshot}, "oweru": {"amount": str(deal.buyer_to_oweru), "bank": deal.oweru_bank_snapshot, "reference": deal.payment_reference}, "acknowledgement": "This is not a tax receipt"}


def financial(*, actor, deal_id, operation, key, payload, policy, mutation):
    return execute(actor_scope=actor.pk, operation=operation, resource=deal_id, key=key, payload=payload, lock=lambda: lock_deal(deal_id), authorize=lambda deal: policy(actor, deal), mutation=mutation)


def submit_proof(*, actor, deal_id, transfer, upload, key, request=None):
    content, mime, digest = validate_document(upload)
    if transfer not in {"OWNER", "OWERU"}:
        raise ValidationError("Invalid transfer type.")
    def mutate(deal):
        if deal.state != "OPEN":
            raise ValidationError("This Deal is complete.")
        proof = PaymentProof.objects.filter(deal=deal, transfer=transfer, digest=digest).first()
        if proof is None:
            media = save_document(actor=actor, owner=deal, upload=upload)
            proof = PaymentProof.objects.create(deal=deal, transfer=transfer, digest=digest, media=media, buyer=actor)
            audit(actor, "payment.proof_submitted", proof, after={"transfer": transfer, "deal_id": str(deal.pk)}, request=request)
        return {"proof_id": str(proof.pk), "media_id": proof.media.media_id, "transfer": transfer}
    return financial(actor=actor, deal_id=deal_id, operation="payment.proof", key=key, payload={"transfer": transfer, "digest": digest, "mime": mime}, policy=lambda a, d: require_deal(a, d, "payment.submit_proof", buyer=True), mutation=mutate)


def confirm_receipt(*, actor, deal_id, transfer, bank_reference, key, request=None):
    if not bank_reference.strip() or transfer not in {"OWNER", "OWERU"}:
        raise ValidationError("A valid transfer and bank reference are required.")
    def policy(a, deal):
        if transfer == "OWERU":
            require_deal(a, deal, "payment.confirm", manager=True)
        else:
            require_deal(a, deal, "deal.update", lister=True)
            if deal.lister_kind != "OWNER":
                raise PermissionDenied("An agent cannot confirm the owner's receipt.")
    def mutate(deal):
        return record_receipt(deal=deal, actor=actor, transfer=transfer, bank_reference=bank_reference, request=request)
    return financial(actor=actor, deal_id=deal_id, operation=f"payment.confirm.{transfer}", key=key, payload={"bank_reference": bank_reference.strip()}, policy=policy, mutation=mutate)


def record_receipt(*, deal, actor, transfer, bank_reference, delivery=None, request=None):
    existing = PaymentConfirmation.objects.filter(deal=deal, transfer=transfer).first()
    if existing:
        if existing.bank_reference != bank_reference.strip():
            raise Conflict("This transfer already has a different receipt confirmation.")
        return {"confirmation_id": str(existing.pk), "transfer": transfer}
    if deal.state != "OPEN":
        raise ValidationError("A completed Deal cannot be changed.")
    amount = deal.buyer_to_owner if transfer == "OWNER" else deal.buyer_to_oweru
    confirmation = PaymentConfirmation.objects.create(deal=deal, actor=actor, transfer=transfer, amount=amount, bank_reference=bank_reference.strip(), delivery=delivery)
    audit(actor, "payment.owner_confirmed" if transfer == "OWNER" else "payment.oweru_confirmed", confirmation, after={"deal_id": str(deal.pk), "amount": str(amount)}, request=request)
    if transfer == "OWERU":
        from .notices import queue_notice
        queue_notice(recipient=deal.buyer, purpose="NON_TAX_ACKNOWLEDGEMENT", deal=deal)
    return {"confirmation_id": str(confirmation.pk), "transfer": transfer}


def record_tax_receipt(*, actor, deal_id, number, kind, upload, key, request=None):
    _, mime, digest = validate_document(upload)
    if kind not in {"EFD", "VFD"} or not number.strip():
        raise ValidationError("An official EFD/VFD receipt number is required.")
    def mutate(deal):
        if not deal.payment_confirmations.filter(transfer="OWERU").exists():
            raise ValidationError("Confirm Oweru's receipt before recording the tax receipt.")
        receipt = OfficialTaxReceipt.objects.filter(deal=deal).first()
        if receipt:
            if receipt.number != number.strip() or receipt.kind != kind or receipt.media.file_hash != digest:
                raise Conflict("This Deal already has a different official receipt.")
        else:
            if OfficialTaxReceipt.objects.filter(number=number.strip()).exists():
                raise ValidationError("Official receipt number already exists.")
            media = save_document(actor=actor, owner=deal, upload=upload)
            receipt = OfficialTaxReceipt.objects.create(deal=deal, number=number.strip(), kind=kind, media=media, actor=actor)
            audit(actor, "official_receipt.recorded", receipt, after={"deal_id": str(deal.pk), "kind": kind}, request=request)
        return {"receipt_id": str(receipt.pk), "number": receipt.number, "media_id": receipt.media.media_id}
    return financial(actor=actor, deal_id=deal_id, operation="payment.tax_receipt", key=key, payload={"number": number.strip(), "kind": kind, "digest": digest}, policy=lambda a, d: require_deal(a, d, "payment.confirm", manager=True), mutation=mutate)


def agreement_action(*, actor, deal_id, action, key, upload=None, request=None):
    payload = {"action": action}
    if upload:
        _, _, payload["digest"] = validate_document(upload)
    def mutate(deal):
        if deal.state != "OPEN":
            raise ValidationError("Completed agreements are immutable.")
        if action == "upload":
            if deal.agreement_id and deal.agreement.file_hash == payload["digest"]:
                return {"agreement_id": deal.agreement.media_id}
            if deal.agreement_approved_at:
                raise ValidationError("Approved agreement cannot be replaced.")
            deal.agreement = save_document(actor=actor, owner=deal, upload=upload)
            deal.agreement_price_confirmed_at = None
            deal.save(update_fields=["agreement", "agreement_price_confirmed_at", "updated_at"])
        elif action == "confirm":
            if not deal.agreement_id:
                raise ValidationError("Upload a signed agreement first.")
            if deal.agreement_price_confirmed_at:
                return {"agreement_id": deal.agreement.media_id}
            deal.agreement_price_confirmed_at = timezone.now()
            deal.save(update_fields=["agreement_price_confirmed_at", "updated_at"])
        elif action == "approve":
            if not deal.agreement_price_confirmed_at:
                raise ValidationError("Lister confirmation of the exact final price is required.")
            if deal.agreement_approved_at:
                return {"agreement_id": deal.agreement.media_id}
            deal.agreement_approved_at, deal.agreement_approved_by = timezone.now(), actor
            deal.save(update_fields=["agreement_approved_at", "agreement_approved_by", "updated_at"])
        else:
            raise ValidationError("Invalid agreement action.")
        audit(actor, {"upload": "agreement.uploaded", "confirm": "agreement.price_confirmed", "approve": "agreement.approved"}[action], deal, after={"final_price": str(deal.final_selling_price)}, request=request)
        return {"agreement_id": deal.agreement.media_id}
    return financial(actor=actor, deal_id=deal_id, operation=f"agreement.{action}", key=key, payload=payload, policy=lambda a, d: require_deal(a, d, "payment.confirm" if action == "approve" else "deal.update", manager=action == "approve", lister=action != "approve"), mutation=mutate)


def working_deadline(start, days):
    if days < 1:
        raise ValidationError("Payout working-day deadline must be positive.")
    current = timezone.localtime(start)
    holidays = {date.fromisoformat(value) for value in settings.PAYOUT_HOLIDAYS}
    remaining = days
    while remaining:
        current += timedelta(days=1)
        if current.weekday() < 5 and current.date() not in holidays:
            remaining -= 1
    return current


def create_payout(*, deal, actor, request=None):
    if deal.state != "COMPLETE" or deal.lister_kind != "AGENT":
        raise ValidationError("Only a completed agent Deal qualifies for payout.")
    payout, created = Payout.objects.get_or_create(deal=deal, defaults={"agent": deal.lister, "amount": deal.agent_payout, "due_at": working_deadline(deal.completed_at, settings.PAYOUT_WORKING_DAYS), "status": "ON_HOLD" if deal.payout_blocks.filter(is_open=True).exists() else "PENDING"})
    if created:
        audit(actor, "payout.created", payout, after={"amount": str(payout.amount), "due_at": payout.due_at.isoformat()}, request=request)
    return payout


def payout_action(*, actor, deal_id, action, key, reason="", bank_reference="", upload=None, request=None):
    payload = {"action": action, "reason": reason.strip(), "bank_reference": bank_reference.strip()}
    if upload:
        _, _, payload["digest"] = validate_document(upload)
    def mutate(deal):
        if action == "create":
            return {"payout_id": str(create_payout(deal=deal, actor=actor, request=request).pk)}
        payout = Payout.objects.select_for_update().get(deal=deal)
        if action == "paid" and payout.status == "PAID":
            if payout.bank_reference != bank_reference.strip() or payout.proof.file_hash != payload.get("digest"):
                raise Conflict("Payout already has different payment evidence.")
            return {"payout_id": str(payout.pk), "status": "PAID"}
        if payout.status == "PAID":
            raise ValidationError("Paid payout is immutable.")
        if action in {"paid", "release"} and deal.payout_blocks.filter(is_open=True).exists():
            raise ValidationError("An open complaint blocks payout.")
        previous = payout.status
        if action == "hold":
            if not reason.strip():
                raise ValidationError("A hold reason is required.")
            if payout.status == "ON_HOLD" and payout.hold_reason == reason.strip():
                return {"payout_id": str(payout.pk), "status": payout.status}
            payout.status, payout.hold_reason = "ON_HOLD", reason.strip()
        elif action == "release":
            if payout.status != "ON_HOLD":
                return {"payout_id": str(payout.pk), "status": payout.status}
            payout.status = "DUE" if payout.due_at <= timezone.now() else "PENDING"
            payout.hold_reason = ""
        elif action == "paid":
            if payout.status == "ON_HOLD" or not bank_reference.strip() or not upload:
                raise ValidationError("Unheld payout, bank reference and proof are required.")
            payout.proof = save_document(actor=actor, owner=deal, upload=upload)
            payout.bank_reference, payout.paid_at, payout.paid_by, payout.status = bank_reference.strip(), timezone.now(), actor, "PAID"
        else:
            raise ValidationError("Invalid payout action.")
        payout.save()
        audit(actor, {"hold": "payout.held", "release": "payout.released", "paid": "payout.paid"}[action], payout, before={"status": previous}, after={"status": payout.status}, request=request)
        return {"payout_id": str(payout.pk), "status": payout.status}
    return financial(actor=actor, deal_id=deal_id, operation=f"payout.{action}", key=key, payload=payload, policy=lambda a, d: require_deal(a, d, "payout.hold" if action in {"hold", "release"} else "payout.record", manager=True), mutation=mutate)


@transaction.atomic
def set_complaint_block(*, actor, deal_id, external_reference, is_open, key, request=None):
    def mutate(deal):
        block, created = PayoutBlock.objects.get_or_create(deal=deal, external_reference=external_reference, defaults={"is_open": is_open})
        if not created and block.is_open != is_open:
            block.is_open = is_open
            block.save(update_fields=["is_open", "updated_at"])
        payout = Payout.objects.select_for_update().filter(deal=deal).first()
        if payout and is_open and payout.status != "PAID" and payout.status != "ON_HOLD":
            previous = payout.status
            payout.status = "ON_HOLD"
            payout.save(update_fields=["status", "updated_at"])
            audit(actor, "payout.held", payout, before={"status": previous}, after={"status": "ON_HOLD", "source": "complaint_policy"}, request=request)
        return {"block_id": str(block.pk), "is_open": block.is_open}
    return financial(actor=actor, deal_id=deal_id, operation="payout.complaint_policy", key=key, payload={"external_reference": external_reference, "is_open": is_open}, policy=lambda a, d: require_deal(a, d, "complaint.handle", manager=True), mutation=mutate)


def mark_due_payouts(at=None):
    now, count = at or timezone.now(), 0
    ids = list(Payout.objects.filter(status="PENDING", due_at__lte=now).values_list("deal_id", flat=True))
    for deal_id in ids:
        with transaction.atomic():
            deal = lock_deal(deal_id)
            payout = Payout.objects.select_for_update().get(deal=deal)
            if payout.status != "PENDING":
                continue
            payout.status = "ON_HOLD" if deal.payout_blocks.filter(is_open=True).exists() else "DUE"
            payout.save(update_fields=["status", "updated_at"])
            audit(None, "payout.held" if payout.status == "ON_HOLD" else "payout.due", payout, after={"status": payout.status})
            count += 1
    return count


def complete_financial_deal(*, actor, deal_id, key, request=None):
    return financial(actor=actor, deal_id=deal_id, operation="deal.complete", key=key, payload={}, policy=lambda a, d: require_deal(a, d, "payment.confirm", manager=True), mutation=lambda d: {"deal_id": str(complete_deal(actor=actor, deal_id=d.pk, request=request).pk), "state": "COMPLETE"})
