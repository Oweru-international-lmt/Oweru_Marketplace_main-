from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.audit.models import AuditLog
from apps.audit.services import create_audit_log
from apps.properties.serializers import RejectUnknownFieldsMixin
from apps.verification.configuration import DEFAULTS, setting, change_setting
from apps.verification.models import VerificationSetting
from . import services


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        actor = services.require_manager(request.user)
        from apps.lister_identity.models import ListerIdentity
        from apps.properties.models import PossibleDuplicate
        from apps.verification.models import VerificationTask, VerificationJob
        from apps.payments.models import Payout, PaymentProof, PaymentConfirmation
        from apps.complaints.models import Complaint
        from apps.notifications.models import Notification
        from apps.listings.models import Listing
        duplicates = PossibleDuplicate.objects.filter(status="PENDING")
        now = timezone.now()
        payload = {"identities_to_approve": ListerIdentity.objects.filter(status="PENDING", submitted_at__isnull=False).count(), "duplicates": duplicates.count(), "flagged_listings": duplicates.filter(Q(property_a__listings__status__in=["ACTIVE", "UNDER_OFFER"]) | Q(property_b__listings__status__in=["ACTIVE", "UNDER_OFFER"])).distinct().count(), "partner_approvals": {"count": 0, "limitation": "Legacy partner models have no pending onboarding approval state."}, "tasks_needing_official": VerificationTask.objects.filter(status="NEEDS_OFFICIAL").count(), "full_check_payments_to_confirm": VerificationJob.objects.filter(status="AWAITING_PAYMENT", payment_proofs__isnull=False, payment_receipt__isnull=True).distinct().count(), "deal_payments_to_confirm": PaymentProof.objects.filter(transfer="OWERU").exclude(deal_id__in=PaymentConfirmation.objects.filter(transfer="OWERU").values("deal_id")).values("deal_id").distinct().count(), "payouts_due": Payout.objects.filter(status__in=["PENDING", "DUE"], due_at__lte=now).count(), "payouts_on_hold": Payout.objects.filter(status="ON_HOLD").count(), "complaints_by_status": {row["status"]: row["count"] for row in Complaint.objects.values("status").annotate(count=Count("pk"))}, "overdue_complaints": Complaint.objects.exclude(status__in=["RESOLVED", "CLOSED"]).filter(resolution_due_at__lt=now).count(), "outbox_waiting": Notification.objects.filter(channel="outbox", status="WAITING").filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now)).count()}
        payload["flagged_listings"] = Listing.objects.filter(status__in=["ACTIVE", "UNDER_OFFER"]).filter(Q(property_id__in=duplicates.values("property_a_id")) | Q(property_id__in=duplicates.values("property_b_id"))).count()
        payload["partner_approvals"]["count"] = None
        payload["partner_approvals"]["available"] = False
        create_audit_log(actor=actor, action="administration.dashboard_viewed", entity_type="ManagementDashboard", request=request)
        return Response(payload)


class SettingInput(RejectUnknownFieldsMixin, serializers.Serializer):
    value = serializers.JSONField()
    version = serializers.IntegerField(min_value=0)


class SettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, setting_key=None):
        actor = services.require_manager(request.user)
        create_audit_log(actor=actor, action="administration.settings_viewed", entity_type="VerificationSetting", request=request)
        if setting_key:
            row = get_object_or_404(VerificationSetting, key=setting_key)
            return Response({"key": row.key, "value": row.value, "version": row.version, "history": list(row.history.values("version", "value", "created_at", "actor_id"))})
        rows = {row.key: row for row in VerificationSetting.objects.all()}
        from apps.commissions.services import current_rate_table
        table = current_rate_table()
        return Response({"settings": [{"key": key, "value": setting(key), "version": rows[key].version if key in rows else 0} for key in DEFAULTS], "commission_settings": {"endpoint": "/api/v1/commissions/", "version": table.version if table else None, "total_rate": str(table.total_rate) if table else None, "policy": "Edit and publish versioned RateTable and RateBand records; historical financial values remain frozen."}})

    def put(self, request, setting_key):
        data = SettingInput(data=request.data)
        data.is_valid(raise_exception=True)
        row = change_setting(actor=request.user, key=setting_key, value=data.validated_data["value"], expected_version=data.validated_data["version"], request=request)
        return Response({"key": row.key, "value": row.value, "version": row.version})


class AccountInput(RejectUnknownFieldsMixin, serializers.Serializer):
    version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=1000)
    active = serializers.BooleanField(required=False)
    full_name = serializers.CharField(max_length=255, required=False)


class StaffInput(RejectUnknownFieldsMixin, serializers.Serializer):
    role = serializers.ChoiceField(choices=["verifier", "marketer"])
    full_name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=30)
    preferred_language = serializers.ChoiceField(choices=["sw", "en"], default="sw")


class AccountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        from apps.accounts.models import User
        from .models import AdministrationHistory
        actor = services.require_manager(request.user, "account.manage")
        row = get_object_or_404(User, pk=user_id)
        create_audit_log(actor=actor, action="sensitive_data.accessed", entity_type="User", entity_id=row.pk, request=request)
        return Response({"id": str(row.pk), "full_name": row.full_name, "email": row.email, "is_active": row.is_active, "account_category": row.account_category, "version": row.administration_version, "history": list(AdministrationHistory.objects.filter(entity_type="User", entity_id=row.pk).values("reason", "before", "after", "created_at", "actor_id"))})

    def post(self, request, user_id=None):
        if user_id is None:
            data = StaffInput(data=request.data)
            data.is_valid(raise_exception=True)
            row = services.create_staff(actor=request.user, values=data.validated_data, request=request)
            return Response({"id": str(row.pk), "version": row.administration_version}, status=201)
        data = AccountInput(data=request.data)
        data.is_valid(raise_exception=True)
        row = services.account_change(actor=request.user, user_id=user_id, request=request, **data.validated_data)
        return Response({"id": str(row.pk), "is_active": row.is_active, "version": row.administration_version})


class ListingInput(RejectUnknownFieldsMixin, serializers.Serializer):
    version = serializers.CharField(max_length=64)
    reason = serializers.CharField(max_length=1000)
    action = serializers.ChoiceField(choices=["suspend", "restore"])


class ListingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, listing_id):
        data = ListingInput(data=request.data)
        data.is_valid(raise_exception=True)
        row = services.listing_change(actor=request.user, listing_id=listing_id, request=request, **data.validated_data)
        return Response({"listing_id": row.listing_id, "status": row.status, "version": row.updated_at.isoformat()})


class AuditView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        actor = services.require_manager(request.user, "audit.view")
        rows = AuditLog.objects.order_by("-created_at")
        if request.query_params.get("entity_id"):
            rows = rows.filter(entity_id=request.query_params["entity_id"])
        create_audit_log(actor=actor, action="sensitive_data.accessed", entity_type="AuditLog", request=request)
        return Response(list(rows.values("id", "actor_id", "action", "entity_type", "entity_id", "before", "after", "created_at")[:100]))
