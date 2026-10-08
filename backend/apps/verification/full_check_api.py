from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework import generics, serializers
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from apps.accounts.models import User
from apps.audit.services import create_audit_log
from apps.leads.policies import authorize, management
from apps.properties.policies import get_active_persisted_actor
from apps.media.storage import get_private_media_storage
from apps.payments.models import ConfirmationDelivery
from .serializers import StrictInputSerializer
from .pagination import VerificationReviewPagination
from .models import VerificationJob, VerificationReport, VerificationNotice
from . import full_check_services as services


def readable_jobs(actor):
    actor = get_active_persisted_actor(actor)
    queryset = VerificationJob.objects.select_related("property", "listing")
    if actor is None:
        return queryset.none()
    if management(actor) and actor.has_marketplace_permission("verification.record_result"):
        return queryset
    query = Q(pk__in=[])
    if actor.has_role("buyer") and actor.has_marketplace_permission("verification.order"):
        query |= Q(buyer=actor)
    if actor.has_role("verifier") and actor.has_marketplace_permission("verification.record_result"):
        query |= Q(verifier=actor)
    return queryset.filter(query)


class FullCheckSerializer(serializers.ModelSerializer):
    property_id = serializers.CharField(source="property.property_id", read_only=True)
    class Meta:
        model = VerificationJob
        fields = ["id", "kind", "property_id", "status", "fee", "scope_snapshot", "payment_reference", "consent_due_at", "completed_at", "expires_at", "invalidated_at", "created_at"]
        read_only_fields = fields


class OrderSerializer(StrictInputSerializer):
    listing_id = serializers.CharField(max_length=50, required=False)
    outside = serializers.JSONField(required=False)
    owner_user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False)
    owner_name = serializers.CharField(max_length=255, required=False)
    owner_phone = serializers.CharField(max_length=30, required=False)
    quote_token = serializers.CharField()


class ProofSerializer(StrictInputSerializer):
    upload = serializers.FileField()


class ReceiptSerializer(StrictInputSerializer):
    amount = serializers.DecimalField(max_digits=18, decimal_places=0, min_value=1)
    reference = serializers.UUIDField()
    bank_reference = serializers.CharField(max_length=255)
    tax_receipt_number = serializers.CharField(max_length=255)
    tax_receipt = serializers.FileField()


class ConsentSerializer(StrictInputSerializer):
    decision = serializers.ChoiceField(choices=["CONFIRM", "DECLINE"])


class ExternalConsentSerializer(ConsentSerializer):
    token = serializers.CharField(max_length=100)


class OwnerContactSerializer(StrictInputSerializer):
    owner_name = serializers.CharField(max_length=255)
    owner_phone = serializers.CharField(max_length=30)


class VerifierSerializer(StrictInputSerializer):
    verifier = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())


class StartSerializer(StrictInputSerializer):
    professional_types = serializers.ListField(child=serializers.ChoiceField(choices=["AFISA_MIPANGO_MIJI", "PLANNER", "SURVEYOR"]), required=False)
    surveyor_capture = serializers.BooleanField(required=False)


class ResultSerializer(StrictInputSerializer):
    result = serializers.ChoiceField(choices=["PASSED", "PROBLEM_FOUND"])
    risk_assessment = serializers.CharField(max_length=20000)
    not_checked = serializers.ListField(child=serializers.CharField(max_length=1000), required=False)


class RefreshSerializer(StrictInputSerializer):
    risk_assessment = serializers.CharField(max_length=20000)


class QuoteView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    def get(self, request):
        return Response(services.quote())


class FullCheckCollectionView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer
    pagination_class = VerificationReviewPagination
    def get(self, request):
        page = self.paginate_queryset(readable_jobs(request.user).order_by("-created_at", "id"))
        return self.get_paginated_response(FullCheckSerializer(page, many=True).data)
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(services.order_full_check(actor=request.user, key=request.headers.get("Idempotency-Key"), request=request, **serializer.validated_data), status=201)


class FullCheckDetailView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FullCheckSerializer
    def get(self, request, job_id):
        job = get_object_or_404(readable_jobs(request.user), pk=job_id)
        services.audit(request.user, "sensitive_data.accessed", job, {"purpose": "full_check_detail"}, request)
        data = self.get_serializer(job).data
        actor = get_active_persisted_actor(request.user)
        if management(actor) or job.verifier_id == actor.pk:
            data["internal_property_flags"] = {"unresolved_adverse_full_check": VerificationJob.objects.filter(property=job.property, status="PROBLEM_FOUND", invalidated_at__isnull=True).exists()}
        if hasattr(job, "result"):
            data["result"] = {"result": job.result.result, "risk_assessment": job.result.risk_assessment, "not_checked": job.result.not_checked}
        data["reports"] = [{"id": str(report.pk), "version": report.version, "language": report.language} for report in job.reports.order_by("version")]
        return Response(data)


class InstructionsView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, job_id):
        return Response(services.payment_instructions(actor=request.user, job_id=job_id, request=request))


class ProofView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProofSerializer
    parser_classes = [MultiPartParser, FormParser]
    def get(self, request, job_id):
        job = financial_job(request.user, job_id)
        services.audit(request.user, "sensitive_data.accessed", job, {"purpose": "full_check_payment_documents"}, request)
        receipt = getattr(job, "payment_receipt", None)
        return Response({"proofs": [{"id": str(row.pk), "document_id": str(row.media_id), "created_at": row.created_at} for row in job.payment_proofs.order_by("created_at")], "tax_receipt": {"number": receipt.tax_receipt_number, "document_id": str(receipt.tax_receipt_id)} if receipt else None})
    def post(self, request, job_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(services.submit_payment_proof(actor=request.user, job_id=job_id, key=request.headers.get("Idempotency-Key"), request=request, **serializer.validated_data), status=201)


def financial_job(actor, job_id):
    actor = get_active_persisted_actor(actor)
    queryset = VerificationJob.objects.all()
    if actor and management(actor) and actor.has_marketplace_permission("payment.confirm"):
        return get_object_or_404(queryset, pk=job_id)
    if actor and actor.has_role("buyer") and actor.has_marketplace_permission("payment.submit_proof"):
        return get_object_or_404(queryset, pk=job_id, buyer=actor)
    return get_object_or_404(queryset.none(), pk=job_id)


class PaymentDocumentView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, job_id, document_id):
        job = financial_job(request.user, job_id)
        from apps.media.models import Media
        ids = list(job.payment_proofs.values_list("media_id", flat=True))
        receipt = getattr(job, "payment_receipt", None)
        if receipt:
            ids.append(receipt.tax_receipt_id)
        media = get_object_or_404(Media.objects.filter(pk__in=ids), pk=document_id)
        services.audit(request.user, "sensitive_data.accessed", media, {"purpose": "full_check_payment_document"}, request)
        return Response({"url": get_private_media_storage().generate_signed_read_url(key=media.file_key)})


class ReceiptView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ReceiptSerializer
    parser_classes = [MultiPartParser, FormParser]
    def post(self, request, job_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(services.confirm_full_check_payment(actor=request.user, job_id=job_id, key=request.headers.get("Idempotency-Key"), request=request, **serializer.validated_data))


class OwnerConsentView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ConsentSerializer
    def get(self, request, job_id):
        from rest_framework.exceptions import PermissionDenied
        job = get_object_or_404(VerificationJob, pk=job_id)
        actor = get_active_persisted_actor(request.user)
        if actor is None or job.owner_user_id != actor.pk:
            raise PermissionDenied("Only the Owner may view this consent request.")
        return Response({"property_id": job.property.property_id, "scope": job.scope_snapshot, "deadline": job.consent_due_at, "status": job.status})
    def post(self, request, job_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(services.owner_consent(actor=request.user, job_id=job_id, request=request, **serializer.validated_data))


class ExternalOwnerConsentView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = ExternalConsentSerializer
    throttle_scope = "confirmation"
    throttle_classes = [ScopedRateThrottle]
    def get(self, request, delivery_id):
        from apps.payments.confirmations import check_token
        row = get_object_or_404(ConfirmationDelivery, pk=delivery_id, purpose="FULL_CHECK_CONSENT")
        check_token(row, request.query_params.get("token"))
        return Response({"purpose": row.purpose, "context": row.context})
    def post(self, request, delivery_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(services.external_owner_consent(delivery_id=delivery_id, key=request.headers.get("Idempotency-Key"), request=request, **serializer.validated_data))


class OwnerContactView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OwnerContactSerializer
    def post(self, request, job_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(services.supply_owner_contact(actor=request.user, job_id=job_id, request=request, **serializer.validated_data))


class VerifierView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = VerifierSerializer
    def post(self, request, job_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(FullCheckSerializer(services.assign_verifier(actor=request.user, job_id=job_id, request=request, **serializer.validated_data)).data)


class StartView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = StartSerializer
    def post(self, request, job_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from .task_api import TaskSerializer
        return Response(TaskSerializer(services.start_tasks(actor=request.user, job_id=job_id, request=request, **serializer.validated_data), many=True).data, status=201)


class ResultView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ResultSerializer
    def post(self, request, job_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(services.finalize_full_check(actor=request.user, job_id=job_id, request=request, **serializer.validated_data))


class RefreshView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RefreshSerializer
    def post(self, request, job_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(FullCheckSerializer(services.refresh_full_check(actor=request.user, job_id=job_id, request=request, **serializer.validated_data)).data)


class ReportView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, job_id, report_id):
        job = get_object_or_404(readable_jobs(request.user), pk=job_id)
        report = get_object_or_404(VerificationReport.objects.select_related("media"), pk=report_id, job=job)
        services.audit(request.user, "sensitive_data.accessed", report, {"purpose": "full_check_report"}, request)
        return Response({"url": get_private_media_storage().generate_signed_read_url(key=report.media.file_key), "version": report.version})


class EligibleProfessionalsView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, job_id):
        from .task_services import require_responsible_verifier
        from apps.professionals.services import eligible_professionals
        from apps.professionals.api import ProfessionalSerializer
        job = get_object_or_404(VerificationJob.objects.select_related("property"), pk=job_id)
        require_responsible_verifier(request.user, job, "verification.assign_task")
        rows = eligible_professionals(property_record=job.property, professional_type=request.query_params.get("type"))
        return Response(ProfessionalSerializer(rows, many=True).data)


class SettingSerializer(StrictInputSerializer):
    value = serializers.JSONField()


class VerificationSettingView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SettingSerializer
    def put(self, request, setting_key):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from .configuration import change_setting
        row = change_setting(actor=request.user, key=setting_key, request=request, **serializer.validated_data)
        return Response({"key": row.key, "value": row.value})


class NotificationView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    pagination_class = VerificationReviewPagination
    def get(self, request):
        actor = get_active_persisted_actor(request.user)
        queryset = VerificationNotice.objects.filter(recipient=actor).order_by("-created_at")
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response([{"id": str(row.pk), "purpose": row.purpose, "job_id": str(row.job_id) if row.job_id else None, "task_id": str(row.task_id) if row.task_id else None, "created_at": row.created_at} for row in page])
