from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.properties.services import get_property_record
from apps.roles.permissions import IsLocalOfficial, IsVerifier

from .models import PropertyVerification
from .pagination import VerificationReviewPagination
from .serializers import (
    DocumentVerificationSubmissionSerializer,
    EmptyVerificationActionSerializer,
    FieldVerificationSubmissionSerializer,
    PropertyVerificationPrivateSerializer,
    PropertyVerificationReviewSerializer,
    PropertyVerificationStatusSerializer,
    VerificationRejectSerializer,
)
from .services import (
    approve_document_verification,
    approve_field_verification,
    get_effective_verification_level,
    reject_document_verification,
    reject_field_verification,
    revoke_document_verification,
    revoke_field_verification,
    submit_document_verification,
    submit_field_verification,
)


class PropertyDocumentVerificationSubmissionView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DocumentVerificationSubmissionSerializer

    @extend_schema(request=DocumentVerificationSubmissionSerializer, responses={201: PropertyVerificationPrivateSerializer})
    def post(self, request, property_id, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        property_record = get_property_record(actor=request.user, property_id=property_id)
        verification = submit_document_verification(
            property_record=property_record,
            submitted_by=request.user,
            evidence=serializer.validated_data["evidence"],
            request=request,
        )
        return Response(PropertyVerificationPrivateSerializer(verification).data, status=status.HTTP_201_CREATED)


class PropertyFieldVerificationSubmissionView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FieldVerificationSubmissionSerializer

    @extend_schema(request=FieldVerificationSubmissionSerializer, responses={201: PropertyVerificationPrivateSerializer})
    def post(self, request, property_id, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        property_record = get_property_record(actor=request.user, property_id=property_id)
        verification = submit_field_verification(
            property_record=property_record,
            submitted_by=request.user,
            evidence=serializer.validated_data["evidence"],
            request=request,
        )
        return Response(PropertyVerificationPrivateSerializer(verification).data, status=status.HTTP_201_CREATED)


class PropertyVerificationStatusView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PropertyVerificationStatusSerializer

    @extend_schema(responses={200: PropertyVerificationStatusSerializer})
    def get(self, request, property_id, *args, **kwargs):
        property_record = get_property_record(actor=request.user, property_id=property_id)
        verifications = PropertyVerification.objects.filter(property=property_record).order_by("-submitted_at", "-id")
        payload = {
            "effective_verification_level": get_effective_verification_level(
                user=request.user,
                property_record=property_record,
            ),
            "verifications": verifications,
        }
        return Response(self.get_serializer(payload).data)


class VerificationReviewQueueView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PropertyVerificationReviewSerializer
    pagination_class = VerificationReviewPagination
    verification_kind = None

    def get_queryset(self):
        return (
            PropertyVerification.objects.select_related("property")
            .filter(kind=self.verification_kind, status=PropertyVerification.Status.PENDING)
            .order_by("submitted_at", "id")
        )

    @extend_schema(responses={200: PropertyVerificationReviewSerializer(many=True)})
    def get(self, request, *args, **kwargs):
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(self.get_queryset(), request, view=self)
        serializer = self.get_serializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class VerificationReviewDetailView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PropertyVerificationReviewSerializer
    verification_kind = None

    def get_verification(self, verification_id):
        try:
            return (
                PropertyVerification.objects.select_related("property")
                .filter(kind=self.verification_kind)
                .get(pk=verification_id)
            )
        except (TypeError, ValueError, PropertyVerification.DoesNotExist) as exc:
            raise NotFound("Property verification was not found.") from exc

    @extend_schema(responses={200: PropertyVerificationReviewSerializer})
    def get(self, request, verification_id, *args, **kwargs):
        return Response(self.get_serializer(self.get_verification(verification_id)).data)


class DocumentVerificationReviewQueueView(VerificationReviewQueueView):
    permission_classes = [IsAuthenticated, IsVerifier]
    verification_kind = PropertyVerification.Kind.DOCUMENT


class DocumentVerificationReviewDetailView(VerificationReviewDetailView):
    permission_classes = [IsAuthenticated, IsVerifier]
    verification_kind = PropertyVerification.Kind.DOCUMENT


class DocumentVerificationApproveView(DocumentVerificationReviewDetailView):
    http_method_names = ["post", "options"]

    @extend_schema(request=EmptyVerificationActionSerializer, responses={200: PropertyVerificationReviewSerializer})
    def post(self, request, verification_id, *args, **kwargs):
        serializer = EmptyVerificationActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        verification = approve_document_verification(
            verification=self.get_verification(verification_id),
            reviewer=request.user,
            request=request,
        )
        return Response(self.get_serializer(verification).data)


class DocumentVerificationRejectView(DocumentVerificationReviewDetailView):
    http_method_names = ["post", "options"]

    @extend_schema(request=VerificationRejectSerializer, responses={200: PropertyVerificationReviewSerializer})
    def post(self, request, verification_id, *args, **kwargs):
        serializer = VerificationRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        verification = reject_document_verification(
            verification=self.get_verification(verification_id),
            reviewer=request.user,
            reason=serializer.validated_data["reason"],
            request=request,
        )
        return Response(self.get_serializer(verification).data)


class DocumentVerificationRevokeView(DocumentVerificationReviewDetailView):
    http_method_names = ["post", "options"]

    @extend_schema(request=EmptyVerificationActionSerializer, responses={200: PropertyVerificationReviewSerializer})
    def post(self, request, verification_id, *args, **kwargs):
        serializer = EmptyVerificationActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        verification = revoke_document_verification(
            verification=self.get_verification(verification_id),
            reviewer=request.user,
            request=request,
        )
        return Response(self.get_serializer(verification).data)


class FieldVerificationReviewQueueView(VerificationReviewQueueView):
    permission_classes = [IsAuthenticated, IsLocalOfficial]
    verification_kind = PropertyVerification.Kind.FIELD


class FieldVerificationReviewDetailView(VerificationReviewDetailView):
    permission_classes = [IsAuthenticated, IsLocalOfficial]
    verification_kind = PropertyVerification.Kind.FIELD


class FieldVerificationApproveView(FieldVerificationReviewDetailView):
    http_method_names = ["post", "options"]

    @extend_schema(request=EmptyVerificationActionSerializer, responses={200: PropertyVerificationReviewSerializer})
    def post(self, request, verification_id, *args, **kwargs):
        serializer = EmptyVerificationActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        verification = approve_field_verification(
            verification=self.get_verification(verification_id),
            reviewer=request.user,
            request=request,
        )
        return Response(self.get_serializer(verification).data)


class FieldVerificationRejectView(FieldVerificationReviewDetailView):
    http_method_names = ["post", "options"]

    @extend_schema(request=VerificationRejectSerializer, responses={200: PropertyVerificationReviewSerializer})
    def post(self, request, verification_id, *args, **kwargs):
        serializer = VerificationRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        verification = reject_field_verification(
            verification=self.get_verification(verification_id),
            reviewer=request.user,
            reason=serializer.validated_data["reason"],
            request=request,
        )
        return Response(self.get_serializer(verification).data)


class FieldVerificationRevokeView(FieldVerificationReviewDetailView):
    http_method_names = ["post", "options"]

    @extend_schema(request=EmptyVerificationActionSerializer, responses={200: PropertyVerificationReviewSerializer})
    def post(self, request, verification_id, *args, **kwargs):
        serializer = EmptyVerificationActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        verification = revoke_field_verification(
            verification=self.get_verification(verification_id),
            reviewer=request.user,
            request=request,
        )
        return Response(self.get_serializer(verification).data)
