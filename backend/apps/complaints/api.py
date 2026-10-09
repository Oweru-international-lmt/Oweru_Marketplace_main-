from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from apps.accounts.models import User
from apps.audit.services import create_audit_log
from apps.media.storage import get_private_media_storage
from apps.leads.policies import authorize, management
from apps.properties.serializers import RejectUnknownFieldsMixin
from .models import Complaint
from . import services


class Intake(RejectUnknownFieldsMixin, serializers.Serializer):
    name = serializers.CharField(max_length=255)
    phone = serializers.CharField(max_length=30)
    email = serializers.EmailField(required=False, allow_blank=True)
    complainant_role = serializers.ChoiceField(choices=["buyer", "owner", "agent", "local_official", "professional", "other"])
    category = serializers.ChoiceField(choices=Complaint.TYPES)
    description = serializers.CharField(max_length=10000)
    property_reference = serializers.CharField(max_length=50, required=False)
    deal_id = serializers.UUIDField(required=False)
    language = serializers.ChoiceField(choices=["sw", "en"], default="sw")


class TransitionInput(RejectUnknownFieldsMixin, serializers.Serializer):
    status = serializers.ChoiceField(choices=Complaint.STATUSES)
    version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=10000)
    outcome = serializers.CharField(max_length=10000, required=False, default="", allow_blank=True)


class AssignmentInput(RejectUnknownFieldsMixin, serializers.Serializer):
    handler_id = serializers.UUIDField()
    version = serializers.IntegerField(min_value=1)
    escalate = serializers.BooleanField(default=False)


class FinalReviewInput(RejectUnknownFieldsMixin, serializers.Serializer):
    token = serializers.CharField(max_length=128)
    reason = serializers.CharField(max_length=10000)


def summary(row):
    return {"id": str(row.pk), "reference": row.reference, "status": row.status, "outcome": row.outcome, "reasons": row.reasons, "version": row.version, "resolution_due_at": row.resolution_due_at}


class IntakeView(APIView):
    permission_classes = [AllowAny]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        response["Referrer-Policy"] = "no-referrer"
        return response

    def post(self, request):
        values = request.data.copy()
        source = values.pop("source", "WEB")
        if isinstance(source, list):
            source = source[0]
        values.pop("evidence", None)
        row = services.lodge(values=values, source=source, actor=request.user, evidence=request.FILES.getlist("evidence"), request=request)
        return Response({**summary(row), "status_link": request.build_absolute_uri(f"/api/v1/complaints/{row.pk}/status/?token={services.token_for(row)}")}, status=201)


class PublicStatusView(APIView):
    permission_classes = [AllowAny]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        response["Referrer-Policy"] = "no-referrer"
        return response

    def get(self, request, complaint_id):
        row = services.public_access(complaint_id, request.query_params.get("token"))
        create_audit_log(action="sensitive_data.accessed", entity_type="Complaint", entity_id=row.pk, after={"purpose": "public_status"}, request=request)
        return Response(summary(row))

    def post(self, request, complaint_id, action):
        token = request.data.get("token")
        if action == "final-review":
            values = FinalReviewInput(data=request.data)
            values.is_valid(raise_exception=True)
            row = services.request_final_review(complaint_id=complaint_id, request=request, **values.validated_data)
            return Response(summary(row))
        row = services.add_response(complaint_id=complaint_id, token=token, text=request.data.get("text", ""), evidence=request.FILES.getlist("evidence"), request=request)
        return Response({"id": str(row.pk)}, status=201)


class DeskView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, complaint_id=None, evidence_id=None):
        actor = authorize(request.user, "complaint.handle")
        if complaint_id is None:
            rows = Complaint.objects.order_by("created_at")
            if not management(actor):
                rows = rows.filter(category="VERIFICATION", route="VERIFIER", handler=actor)
            return Response([{**summary(row), "route": row.route, "overdue": row.status not in {"RESOLVED", "CLOSED"} and row.resolution_due_at < timezone.now()} for row in rows[:100]])
        row = get_object_or_404(Complaint, pk=complaint_id)
        services.require_handler(actor, row)
        create_audit_log(actor=actor, action="sensitive_data.accessed", entity_type="Complaint", entity_id=row.pk, request=request)
        if evidence_id:
            evidence = get_object_or_404(row.evidence, pk=evidence_id)
            return Response({"url": get_private_media_storage().generate_signed_read_url(key=evidence.media.file_key, expires_in=settings.MEDIA_SIGNED_URL_TTL_SECONDS)})
        return Response({**summary(row), "name": row.name, "phone": row.phone, "description": row.description, "category": row.category, "handler": str(row.handler_id) if row.handler_id else None, "evidence": [str(item.pk) for item in row.evidence.all()], "responses": [{"text": response.text, "from_complainant": response.from_complainant, "date": response.created_at} for response in row.responses.all()], "history": list(row.history.values("status", "reason", "version", "created_at"))})

    def post(self, request, complaint_id, action):
        if action == "response":
            row = services.add_response(actor=request.user, complaint_id=complaint_id, text=request.data.get("text", ""), evidence=request.FILES.getlist("evidence"), request=request)
            return Response({"id": str(row.pk)}, status=201)
        if action == "assign":
            values = AssignmentInput(data=request.data)
            values.is_valid(raise_exception=True)
            data = dict(values.validated_data)
            handler = get_object_or_404(User, pk=data.pop("handler_id"))
            row = services.assign(actor=request.user, complaint_id=complaint_id, handler=handler, request=request, **data)
        else:
            from rest_framework.exceptions import ValidationError
            if action != "transition":
                raise ValidationError("Unknown complaint action.")
            values = TransitionInput(data=request.data)
            values.is_valid(raise_exception=True)
            row = services.transition(actor=request.user, complaint_id=complaint_id, request=request, **values.validated_data)
        return Response(summary(row))
