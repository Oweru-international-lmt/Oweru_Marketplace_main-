from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.accounts.models import User
from apps.leads.policies import authorize, management
from apps.leads.services import audit
from apps.deals.models import Deal
from apps.deals.serializers import DealSerializer, BuyerDealSerializer
from apps.deals.services import reprice, require_deal, lock_deal
from apps.listings.serializers import EmptyActionSerializer
from apps.media.models import Media
from apps.media.storage import get_private_media_storage
from .models import BankAccount, ConfirmationDelivery, Payout, PaymentProof, OfficialTaxReceipt, FinancialNotice
from . import services, confirmations, serializers
from .idempotency import execute


def validated(cls, request):
    serializer = cls(data=request.data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def key(request):
    return request.headers.get("Idempotency-Key")


def deal_access(actor, queryset):
    actor = User.objects.filter(pk=actor.pk, is_active=True).first()
    if actor is None:
        raise PermissionDenied("Active account required.")
    # Buyer read is payment context, not a fabricated deal.view grant.
    if management(actor):
        authorize(actor, "deal.view")
        return queryset
    condition = Q(pk__in=[])
    if actor.has_marketplace_permission("deal.view"):
        condition |= Q(lister=actor)
    if actor.has_marketplace_permission("payment.submit_proof"):
        condition |= Q(buyer=actor)
    return queryset.filter(condition)


class DealListView(APIView):
    def get(self, request):
        deals = deal_access(request.user, Deal.objects.select_related("listing").all())
        return Response([(BuyerDealSerializer if d.buyer_id == request.user.pk else DealSerializer)(d).data for d in deals])


class DealDetailView(APIView):
    def get(self, request, pk):
        deal = get_object_or_404(deal_access(request.user, Deal.objects.select_related("listing")), pk=pk)
        audit(request.user, "sensitive_data.accessed", deal, after={"purpose": "deal_financial_detail"}, request=request)
        return Response((BuyerDealSerializer if deal.buyer_id == request.user.pk else DealSerializer)(deal).data)


class InstructionsView(APIView):
    def get(self, request, pk):
        get_object_or_404(Deal, pk=pk)
        return Response(services.instructions(actor=request.user, deal_id=pk, request=request))


class ProofView(APIView):
    def post(self, request, pk):
        values = validated(serializers.ProofSerializer, request)
        get_object_or_404(Deal, pk=pk)
        return Response(services.submit_proof(actor=request.user, deal_id=pk, transfer=values["transfer"], upload=values["file"], key=key(request), request=request))


class ReceiptView(APIView):
    def post(self, request, pk, transfer):
        values = validated(serializers.ReceiptSerializer, request)
        get_object_or_404(Deal, pk=pk)
        return Response(services.confirm_receipt(actor=request.user, deal_id=pk, transfer=transfer.upper(), key=key(request), request=request, **values))


class TaxReceiptView(APIView):
    def post(self, request, pk):
        values = validated(serializers.TaxSerializer, request)
        get_object_or_404(Deal, pk=pk)
        upload = values.pop("file")
        return Response(services.record_tax_receipt(actor=request.user, deal_id=pk, upload=upload, key=key(request), request=request, **values))


class AgreementView(APIView):
    def post(self, request, pk, action):
        get_object_or_404(Deal, pk=pk)
        if action == "upload":
            upload = validated(serializers.AgreementSerializer, request)["file"]
        elif action in {"confirm", "approve"}:
            validated(serializers.ExactPriceSerializer, request)
            upload = None
        else:
            raise ValidationError("Invalid agreement action.")
        return Response(services.agreement_action(actor=request.user, deal_id=pk, action=action, upload=upload, key=key(request), request=request))


class CompleteView(APIView):
    def post(self, request, pk):
        validated(EmptyActionSerializer, request)
        get_object_or_404(Deal, pk=pk)
        return Response(services.complete_financial_deal(actor=request.user, deal_id=pk, key=key(request), request=request))


class RepriceView(APIView):
    def post(self, request, pk):
        from rest_framework import serializers as drf
        from apps.listings.serializers import RejectUnknownFieldsMixin
        class Input(RejectUnknownFieldsMixin, drf.Serializer):
            final_selling_price = drf.DecimalField(max_digits=18, decimal_places=0, min_value=1)
        values = validated(Input, request)
        get_object_or_404(Deal, pk=pk)
        result = services.financial(actor=request.user, deal_id=pk, operation="deal.reprice", key=key(request), payload={"price": str(values["final_selling_price"])}, policy=lambda a, d: require_deal(a, d, "deal.update", lister=True), mutation=lambda d: {"deal_id": str(reprice(actor=request.user, deal_id=d.pk, request=request, **values).pk), "final_selling_price": str(values["final_selling_price"])})
        return Response(result)


class BankView(APIView):
    def get(self, request):
        actor = authorize(request.user, "account.view")
        bank = get_object_or_404(BankAccount, user=actor)
        audit(actor, "sensitive_data.accessed", bank, after={"purpose": "own_bank_account"}, request=request)
        return Response(services.bank_data(bank))

    @transaction.atomic
    def put(self, request):
        actor = authorize(request.user, "account.update")
        if not actor.has_role("owner") and not actor.has_role("agent"):
            raise PermissionDenied("A lister account is required.")
        values = validated(serializers.BankSerializer, request)
        def mutation(locked):
            bank = BankAccount.objects.filter(user=locked).first()
            if bank and services.bank_data(bank) == values:
                return {"bank_account_id": str(bank.pk)}
            bank, _ = BankAccount.objects.update_or_create(user=locked, defaults=values)
            audit(actor, "bank_account.updated", bank, after={"holder": "self"}, request=request)
            return {"bank_account_id": str(bank.pk)}
        return Response(execute(actor_scope=actor.pk, operation="bank.self", resource=actor.pk, key=key(request), payload=values, lock=lambda: User.objects.select_for_update().get(pk=actor.pk), authorize=lambda locked: authorize(locked, "account.update"), mutation=mutation))


class ManagementBankView(APIView):
    def get(self, request, pk):
        actor = authorize(request.user, "payment.confirm")
        if not management(actor):
            raise PermissionDenied("Management required.")
        bank = get_object_or_404(BankAccount, pk=pk)
        audit(actor, "sensitive_data.accessed", bank, after={"purpose": "management_bank_review"}, request=request)
        return Response(services.bank_data(bank))


class OweruBankView(APIView):
    @transaction.atomic
    def put(self, request):
        actor = authorize(request.user, "payment.confirm")
        if not management(actor):
            raise PermissionDenied("Management required.")
        values = validated(serializers.BankSerializer, request)
        def mutation(locked):
            bank = BankAccount.objects.filter(is_oweru=True).first()
            if bank and services.bank_data(bank) == values:
                return {"bank_account_id": str(bank.pk)}
            bank, _ = BankAccount.objects.update_or_create(is_oweru=True, defaults=values)
            audit(actor, "bank_account.updated", bank, after={"holder": "oweru"}, request=request)
            return {"bank_account_id": str(bank.pk)}
        return Response(execute(actor_scope=actor.pk, operation="bank.oweru", resource=actor.pk, key=key(request), payload=values, lock=lambda: User.objects.select_for_update().get(pk=actor.pk), authorize=lambda locked: authorize(locked, "payment.confirm"), mutation=mutation))


class ConfirmationRequestView(APIView):
    def post(self, request):
        values = validated(serializers.RequestConfirmationSerializer, request)
        return Response(confirmations.request_confirmation(actor=request.user, request=request, **values), status=201)


class OutboxView(APIView):
    def get(self, request):
        actor = authorize(request.user, "outbox.send")
        if not management(actor):
            raise PermissionDenied("Authorized Oweru Management required.")
        rows = ConfirmationDelivery.objects.filter(consumed_at__isnull=True, expires_at__gt=services.timezone.now())
        audit(actor, "sensitive_data.accessed", actor, after={"purpose": "confirmation_outbox"}, request=request)
        from urllib.parse import urlencode
        return Response([{"id": str(row.pk), "recipient": row.recipient, "purpose": row.purpose, "context": row.context, "confirmation_link": settings_confirmation_link(row, urlencode), "sent_at": row.sent_at, "expires_at": row.expires_at} for row in rows])


def settings_confirmation_link(row, urlencode):
    from django.conf import settings
    if not settings.OWNER_CONFIRMATION_URL:
        raise ValidationError("OWNER_CONFIRMATION_URL must be configured before external delivery.")
    return settings.OWNER_CONFIRMATION_URL + ("&" if "?" in settings.OWNER_CONFIRMATION_URL else "?") + urlencode({"delivery": str(row.pk), "token": row.delivery_token})


class SentView(APIView):
    def post(self, request, pk):
        validated(EmptyActionSerializer, request)
        get_object_or_404(ConfirmationDelivery, pk=pk)
        return Response(confirmations.mark_sent(actor=request.user, delivery_id=pk, request=request))


class DecisionView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "confirmation"
    throttle_classes = [ScopedRateThrottle]
    def get(self, request, pk):
        row = get_object_or_404(ConfirmationDelivery, pk=pk)
        confirmations.check_token(row, request.query_params.get("token"))
        return Response({"purpose": row.purpose, "context": row.context})

    def post(self, request, pk):
        values = validated(serializers.DecisionSerializer, request)
        get_object_or_404(ConfirmationDelivery, pk=pk)
        return Response(confirmations.decide(delivery_id=pk, key=key(request), request=request, **values))


class PayoutListView(APIView):
    def get(self, request):
        actor = User.objects.get(pk=request.user.pk, is_active=True)
        if management(actor):
            authorize(actor, "payout.record")
            payouts = Payout.objects.all()
        else:
            authorize(actor, "deal.view")
            payouts = Payout.objects.filter(agent=actor)
        return Response([{"id": str(p.pk), "deal_id": str(p.deal_id), "amount": str(p.amount), "status": p.status, "due_at": p.due_at, "paid_at": p.paid_at, "hold_reason": p.hold_reason} for p in payouts])


class PayoutHistoryView(APIView):
    def get(self, request, pk):
        actor = User.objects.filter(pk=request.user.pk, is_active=True).first()
        if actor is None:
            raise PermissionDenied("Active account required.")
        payout = get_object_or_404(Payout, deal_id=pk)
        if management(actor):
            authorize(actor, "payout.record")
        else:
            authorize(actor, "deal.view")
            if payout.agent_id != actor.pk:
                raise PermissionDenied("Only your own payout history is available.")
        from apps.audit.models import AuditLog
        events = AuditLog.objects.filter(entity_type="Payout", entity_id=str(payout.pk)).order_by("created_at")
        return Response([{"action": event.action, "before": event.before, "after": event.after, "created_at": event.created_at} for event in events])


class NoticesView(APIView):
    def get(self, request):
        from urllib.parse import urlencode
        actor = authorize(request.user, "outbox.send")
        if not management(actor):
            raise PermissionDenied("Oweru Management required.")
        result = []
        for notice in FinancialNotice.objects.filter(sent_at__isnull=True).select_related("recipient", "lead", "deal"):
            texts = {
                "LEAD_CREATED": f"A new Marketplace lead is available: {notice.lead_id}.",
                "PAYMENT_INSTRUCTIONS": f"Your bank-transfer instructions are available in your Marketplace Deal: {notice.deal_id}.",
                "FULL_CHECK_OFFER": f"A full ownership check is offered for your Marketplace Deal: {notice.deal_id}. Ordering is provided by the future verification workflow.",
                "NON_TAX_ACKNOWLEDGEMENT": f"Oweru recorded receipt for your Marketplace Deal: {notice.deal_id}. This is not a tax receipt.",
            }
            text = texts.get(notice.purpose, notice.purpose)
            result.append({"id": str(notice.pk), "purpose": notice.purpose, "recipient": notice.recipient.phone, "message": text, "whatsapp_url": "https://wa.me/" + notice.recipient.phone.lstrip("+") + "?" + urlencode({"text": text})})
        audit(actor, "sensitive_data.accessed", actor, after={"purpose": "financial_notice_outbox"}, request=request)
        return Response(result)


class NoticeSentView(APIView):
    @transaction.atomic
    def post(self, request, pk):
        validated(EmptyActionSerializer, request)
        actor = authorize(request.user, "outbox.send")
        if not management(actor):
            raise PermissionDenied("Oweru Management required.")
        notice = get_object_or_404(FinancialNotice.objects.select_for_update(), pk=pk)
        if not notice.sent_at:
            notice.sent_at, notice.sent_by = services.timezone.now(), actor
            notice.save(update_fields=["sent_at", "sent_by", "updated_at"])
            audit(actor, "financial_notice.sent", notice, after={"purpose": notice.purpose}, request=request)
        return Response({"notice_id": str(notice.pk), "sent_at": notice.sent_at})


class PayoutActionView(APIView):
    def post(self, request, pk, action):
        values = validated(serializers.PayoutPaidSerializer if action == "paid" else serializers.HoldSerializer if action == "hold" else EmptyActionSerializer, request)
        get_object_or_404(Deal, pk=pk)
        upload = values.pop("file", None)
        return Response(services.payout_action(actor=request.user, deal_id=pk, action=action, upload=upload, key=key(request), request=request, **values))


class DocumentAccessView(APIView):
    def get(self, request, pk, media_id):
        deal = get_object_or_404(deal_access(request.user, Deal.objects.all()), pk=pk)
        allowed = {deal.agreement_id}
        proofs = deal.payment_proofs
        if deal.buyer_id == request.user.pk:
            allowed.update(proofs.values_list("media_id", flat=True))
        elif management(request.user):
            authorize(request.user, "payment.confirm")
            allowed.update(proofs.values_list("media_id", flat=True))
        if hasattr(deal, "tax_receipt"):
            allowed.add(deal.tax_receipt.media_id)
        if hasattr(deal, "payout") and (deal.lister_id == request.user.pk or management(request.user)):
            allowed.add(deal.payout.proof_id)
        media = get_object_or_404(Media, media_id=media_id, pk__in=allowed)
        audit(request.user, "sensitive_data.accessed", media, after={"purpose": "financial_document"}, request=request)
        return Response({"media_id": media.media_id, "url": get_private_media_storage().generate_signed_read_url(key=media.file_key)})
