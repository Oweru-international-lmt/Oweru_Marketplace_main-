from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import serializers
from rest_framework.exceptions import ValidationError, PermissionDenied
from apps.audit.services import create_audit_log
from apps.leads.policies import authorize, management
from apps.properties.serializers import RejectUnknownFieldsMixin
from .models import Notification, MessageTemplate
from . import services
from .catalog import DEFAULTS


class ContactSelfServiceView(APIView):
    from rest_framework.permissions import AllowAny
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, listing_id):
        from urllib.parse import quote
        from apps.listings.services import get_public_listing
        row = get_public_listing(listing_id=listing_id)
        language = request.query_params.get("language", "sw")
        text, _ = services.render("CONTACT_LISTER", language, {"reference": row.listing_id, "link": services.public_link(f"/api/v1/public/listings/{row.listing_id}/")})
        return Response({"whatsapp_link": f"https://wa.me/{row.lister.phone.lstrip('+')}?text={quote(text)}"})


class InboxView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        actor = authorize(request.user, "account.view")
        rows = Notification.objects.filter(recipient=actor, channel="screen").order_by("-created_at")[:100]
        return Response([{"id": str(row.pk), "purpose": row.purpose, "message": row.message, "created_at": row.created_at, "read_at": row.read_at} for row in rows])

    @transaction.atomic
    def post(self, request, notification_id):
        actor = authorize(request.user, "account.view")
        if request.data:
            raise ValidationError("Read action accepts no client fields.")
        row = get_object_or_404(Notification.objects.select_for_update(), pk=notification_id, recipient=actor, channel="screen")
        row.read_at = row.read_at or timezone.now()
        row.save(update_fields=["read_at", "updated_at"])
        create_audit_log(actor=actor, action="notification.read", entity_type="Notification", entity_id=row.pk, request=request)
        return Response({"id": str(row.pk), "read_at": row.read_at})


class PaymentSelfServiceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, deal_id):
        from urllib.parse import quote
        from apps.deals.models import Deal
        from apps.deals.services import require_deal
        row = get_object_or_404(Deal, pk=deal_id)
        actor = require_deal(request.user, row, "deal.view", lister=True)
        link = services.public_link(f"/api/v1/deals/{row.pk}/payment-instructions/")
        text, _ = services.render("PAYMENT_INSTRUCTIONS", row.buyer.preferred_language, {"reference": str(row.pk), "link": link})
        create_audit_log(actor=actor, action="notification.self_service_created", entity_type="Deal", entity_id=row.pk, request=request)
        return Response({"whatsapp_link": f"https://wa.me/{row.buyer.phone.lstrip('+')}?text={quote(text)}"})


class OutboxView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        actor = services.outbox_actor(request.user)
        rows = Notification.objects.filter(channel="outbox", status="SENT" if request.query_params.get("history") == "1" else "WAITING").order_by("created_at")[:100]
        result = [payload for row in rows if (payload := services.outbox_payload(row, request)) is not None]
        create_audit_log(actor=actor, action="sensitive_data.accessed", entity_type="Notification", after={"purpose": "outbox"}, request=request)
        return Response(result)

    def post(self, request, notification_id):
        if request.data:
            raise ValidationError("Manual sent action accepts no client delivery fields.")
        row = services.mark_sent(actor=request.user, notification_id=notification_id, request=request)
        return Response({"id": str(row.pk), "status": row.status, "sent_at": row.sent_at})


class TemplateInput(RejectUnknownFieldsMixin, serializers.Serializer):
    en = serializers.CharField(max_length=10000)
    sw = serializers.CharField(max_length=10000)
    version = serializers.IntegerField(min_value=0)


class TemplateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        actor = authorize(request.user, "settings.manage")
        if not management(actor):
            raise PermissionDenied()
        rows = {row.key: row for row in MessageTemplate.objects.all()}
        return Response([{"key": key, "version": rows[key].version if key in rows else 0, "en": rows[key].en if key in rows else values["en"], "sw": rows[key].sw if key in rows else values["sw"]} for key, values in DEFAULTS.items()])

    def put(self, request, template_key):
        serializer = TemplateInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = services.change_template(actor=request.user, key=template_key, request=request, **serializer.validated_data)
        return Response({"key": row.key, "version": row.version})
