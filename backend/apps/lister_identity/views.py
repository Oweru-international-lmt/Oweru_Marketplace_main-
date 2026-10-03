from drf_spectacular.utils import extend_schema
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.audit.services import record_sensitive_access
from apps.roles.permissions import IsManagement

from .models import ListerIdentity
from .serializers import (
    ListerIdentityInputSerializer,
    ListerIdentityManagementSerializer,
    ListerIdentityManagementQueueSerializer,
    ListerIdentityPrivateSerializer,
    ListerIdentityRejectSerializer,
    PublicListerProfileSerializer,
)
from .services import (
    approve_lister_identity,
    create_lister_identity,
    get_lister_identity,
    get_public_lister_identity,
    reject_lister_identity,
    submit_lister_identity,
    update_lister_identity,
)


class ListerIdentityCreateView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ListerIdentityInputSerializer

    @extend_schema(request=ListerIdentityInputSerializer, responses={201: ListerIdentityPrivateSerializer})
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identity = create_lister_identity(user=request.user, request=request, **serializer.validated_data)
        return Response(ListerIdentityPrivateSerializer(identity).data, status=status.HTTP_201_CREATED)


class ListerIdentityMeView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: ListerIdentityPrivateSerializer})
    def get(self, request, *args, **kwargs):
        identity = get_lister_identity(user=request.user)
        return Response(ListerIdentityPrivateSerializer(identity).data)

    @extend_schema(request=ListerIdentityInputSerializer, responses={200: ListerIdentityPrivateSerializer})
    def patch(self, request, *args, **kwargs):
        serializer = ListerIdentityInputSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        identity = update_lister_identity(user=request.user, request=request, **serializer.validated_data)
        return Response(ListerIdentityPrivateSerializer(identity).data)


class ListerIdentitySubmitView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: ListerIdentityPrivateSerializer})
    def post(self, request, *args, **kwargs):
        identity = submit_lister_identity(user=request.user, request=request)
        return Response(ListerIdentityPrivateSerializer(identity).data)


class ManagementListerIdentityListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsManagement]
    serializer_class = ListerIdentityManagementQueueSerializer

    def get_queryset(self):
        return (
            ListerIdentity.objects.select_related("user", "reviewed_by")
            .filter(status=ListerIdentity.Status.PENDING, submitted_at__isnull=False)
            .order_by("submitted_at", "created_at", "id")
        )

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        record_sensitive_access(
            actor=request.user,
            entity_type="ListerIdentity",
            entity_id="",
            after={"access_type": "management_review_queue", "purpose": "identity_review"},
            request=request,
        )
        return response


class ManagementListerIdentityDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, IsManagement]
    serializer_class = ListerIdentityManagementSerializer
    queryset = ListerIdentity.objects.select_related("user", "reviewed_by")

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        identity = self.get_object()
        record_sensitive_access(
            actor=request.user,
            entity_type="ListerIdentity",
            entity_id=identity.pk,
            after={"access_type": "management_identity_detail", "purpose": "identity_review"},
            request=request,
        )
        return response


class ManagementListerIdentityApproveView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsManagement]

    @extend_schema(request=None, responses={200: ListerIdentityManagementSerializer})
    def post(self, request, pk, *args, **kwargs):
        identity = get_object_or_404(ListerIdentity, pk=pk)
        identity = approve_lister_identity(identity=identity, reviewed_by=request.user, request=request)
        return Response(ListerIdentityManagementSerializer(identity).data)


class ManagementListerIdentityRejectView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsManagement]
    serializer_class = ListerIdentityRejectSerializer

    @extend_schema(request=ListerIdentityRejectSerializer, responses={200: ListerIdentityManagementSerializer})
    def post(self, request, pk, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identity = get_object_or_404(ListerIdentity, pk=pk)
        identity = reject_lister_identity(
            identity=identity,
            reviewed_by=request.user,
            reason=serializer.validated_data["reason"],
            request=request,
        )
        return Response(ListerIdentityManagementSerializer(identity).data)


class PublicListerProfileView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = PublicListerProfileSerializer

    @extend_schema(responses={200: PublicListerProfileSerializer})
    def get(self, request, identity_id, *args, **kwargs):
        identity, lister_roles = get_public_lister_identity(identity_id=identity_id)
        serializer = self.get_serializer(identity, context={"lister_roles": lister_roles})
        return Response(serializer.data)
