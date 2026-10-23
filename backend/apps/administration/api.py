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
        from apps.local_officials.models import LocalOfficialProfile
        from apps.localities.models import Locality
        payload["partner_approvals"] = {"count": LocalOfficialProfile.objects.filter(status="AWAITING_APPROVAL").count(), "available": True}
        payload["localities_to_approve"] = Locality.objects.filter(approved=False).count()
        payload["oldest"] = oldest_items(now)
        create_audit_log(actor=actor, action="administration.dashboard_viewed", entity_type="ManagementDashboard", request=request)
        return Response(payload)


def oldest_items(now, limit=8):
    """ADM-01: the longest-waiting item in each queue, oldest first, with the page to open."""
    from apps.lister_identity.models import ListerIdentity
    from apps.properties.models import PossibleDuplicate
    from apps.verification.models import VerificationJob
    from apps.payments.models import Payout, PaymentProof, PaymentConfirmation
    from apps.complaints.models import Complaint
    from apps.local_officials.models import LocalOfficialProfile
    from apps.localities.models import Locality
    rows = []
    identity = ListerIdentity.objects.filter(status="PENDING", submitted_at__isnull=False).select_related("user").order_by("submitted_at").first()
    if identity:
        rows.append({"queue": "identities", "reference": identity.user.full_name, "since": identity.submitted_at, "link": f"/staff/identities/{identity.pk}"})
    duplicate = PossibleDuplicate.objects.filter(status="PENDING").select_related("property_a", "property_b").order_by("created_at").first()
    if duplicate:
        rows.append({"queue": "duplicates", "reference": f"{duplicate.property_a.property_id} / {duplicate.property_b.property_id}", "since": duplicate.created_at, "link": f"/staff/duplicates/{duplicate.pk}"})
    official = LocalOfficialProfile.objects.filter(status="AWAITING_APPROVAL").select_related("user", "locality").order_by("created_at").first()
    if official:
        place = f", {official.locality.name}" if official.locality_id else ""
        rows.append({"queue": "partners", "reference": f"{official.user.full_name}{place}", "since": official.created_at, "link": "/staff/partners"})
    locality = Locality.objects.filter(approved=False).select_related("ward").order_by("created_at").first()
    if locality:
        rows.append({"queue": "localities", "reference": f"{locality.name}, {locality.ward.name}", "since": locality.created_at, "link": "/staff/approvals"})
    job = VerificationJob.objects.filter(status="AWAITING_PAYMENT", payment_proofs__isnull=False, payment_receipt__isnull=True).select_related("property").order_by("created_at").first()
    if job:
        rows.append({"queue": "full_check_payments", "reference": job.property.property_id, "since": job.created_at, "link": f"/staff/full-checks/{job.pk}"})
    proof = PaymentProof.objects.filter(transfer="OWERU").exclude(deal_id__in=PaymentConfirmation.objects.filter(transfer="OWERU").values("deal_id")).select_related("deal").order_by("created_at").first()
    if proof:
        rows.append({"queue": "deal_payments", "reference": proof.deal.payment_reference, "since": proof.created_at, "link": f"/staff/deals/{proof.deal_id}"})
    payout = Payout.objects.filter(status__in=["PENDING", "DUE"], due_at__lte=now).select_related("deal").order_by("due_at").first()
    if payout:
        rows.append({"queue": "payouts", "reference": payout.deal.payment_reference, "since": payout.due_at, "link": "/staff/payouts"})
    complaint = Complaint.objects.exclude(status__in=["RESOLVED", "CLOSED"]).order_by("created_at").first()
    if complaint:
        rows.append({"queue": "complaints", "reference": complaint.reference, "since": complaint.created_at, "link": f"/staff/complaints/{complaint.pk}"})
    return sorted(rows, key=lambda row: row["since"])[:limit]


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
            return Response({"key": row.key, "value": row.value, "version": row.version, "history": [{"version": item.version, "value": item.value, "created_at": item.created_at, "actor": item.actor.full_name} for item in row.history.select_related("actor").order_by("-version")]})
        rows = {row.key: row for row in VerificationSetting.objects.select_related("changed_by")}
        from apps.commissions.services import current_rate_table
        from .examples import as_payload
        table = current_rate_table()
        settings_rows = [{"key": key, "value": setting(key), "version": rows[key].version if key in rows else 0, "changed_by": rows[key].changed_by.full_name if key in rows and rows[key].changed_by_id else "", "changed_at": rows[key].updated_at if key in rows else None} for key in DEFAULTS]
        return Response({"settings": settings_rows, "is_director": actor.management_position == "DIRECTOR", "examples": as_payload(), "commission_settings": {"endpoint": "/api/v1/commissions/", "version": table.version if table else None, "total_rate": str(table.total_rate) if table else None, "policy": "Edit and publish versioned RateTable and RateBand records; historical financial values remain frozen."}})

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

    def get(self, request, listing_id):
        """LST-12: what Management sees before suspending or restoring, with the version to send back."""
        from apps.listings.models import Listing
        actor = services.require_manager(request.user, "listing.suspend")
        row = get_object_or_404(Listing.objects.select_related("lister", "property__locality", "property__district"), listing_id=listing_id)
        create_audit_log(actor=actor, action="sensitive_data.accessed", entity_type="Listing", entity_id=row.pk, after={"purpose": "listing_action_lookup"}, request=request)
        place = ", ".join(part for part in [row.property.locality.name if row.property.locality_id else "", row.property.district.name if row.property.district_id else ""] if part)
        return Response({"listing_id": row.listing_id, "status": row.status, "property_id": row.property.property_id, "category": row.property.category, "area": place, "lister": row.lister.full_name, "lister_kind": row.lister_kind, "created_at": row.created_at, "version": row.updated_at.isoformat()})

    def post(self, request, listing_id):
        data = ListingInput(data=request.data)
        data.is_valid(raise_exception=True)
        row = services.listing_change(actor=request.user, listing_id=listing_id, request=request, **data.validated_data)
        return Response({"listing_id": row.listing_id, "status": row.status, "version": row.updated_at.isoformat()})


class AuditView(APIView):
    """ADM-04: who did what to which record, newest first, with filters and the before and after."""
    permission_classes = [IsAuthenticated]
    PAGE = 50

    def get(self, request):
        from datetime import datetime, time
        from django.utils.dateparse import parse_date
        actor = services.require_manager(request.user, "audit.view")
        params = request.query_params
        rows = AuditLog.objects.select_related("actor").order_by("-created_at")
        if params.get("entity_id"):
            rows = rows.filter(entity_id=params["entity_id"])
        if params.get("entity_type"):
            rows = rows.filter(entity_type=params["entity_type"])
        if params.get("actor"):
            rows = rows.filter(actor_id=params["actor"])
        if params.get("action"):
            rows = rows.filter(action__startswith=params["action"])
        if params.get("q"):
            rows = rows.filter(Q(action__icontains=params["q"]) | Q(entity_id__icontains=params["q"]) | Q(actor__full_name__icontains=params["q"]))
        for key, bound, lookup in (("date_from", time.min, "created_at__gte"), ("date_to", time.max, "created_at__lte")):
            day = parse_date(params.get(key) or "")
            if day:
                rows = rows.filter(**{lookup: timezone.make_aware(datetime.combine(day, bound))})
        try:
            page = max(1, int(params.get("page", 1)))
        except ValueError:
            page = 1
        start = (page - 1) * self.PAGE
        chunk = list(rows[start:start + self.PAGE + 1])
        create_audit_log(actor=actor, action="sensitive_data.accessed", entity_type="AuditLog", request=request)
        return Response({
            "results": [{"id": str(row.pk), "actor_id": str(row.actor_id) if row.actor_id else None, "actor": row.actor.full_name if row.actor_id else "", "action": row.action, "entity_type": row.entity_type, "entity_id": row.entity_id, "before": row.before, "after": row.after, "created_at": row.created_at} for row in chunk[:self.PAGE]],
            "page": page,
            "has_next": len(chunk) > self.PAGE,
            "groups": sorted({action.split(".")[0] for action in AuditLog.objects.order_by().values_list("action", flat=True).distinct()}),
        })
