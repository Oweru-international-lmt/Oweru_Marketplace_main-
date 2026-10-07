from django.db.models import BooleanField, Case, Q, Value, When
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.roles.permissions import IsManagement

from .models import LocalOfficialProfile, OfficialJurisdictionAssignment
from .pagination import LocalOfficialPagination
from .serializers import (
    JurisdictionAssignmentInputSerializer,
    JurisdictionAssignmentManagementSerializer,
    JurisdictionAssignmentSelfSerializer,
    LocalOfficialProfileCreateSerializer,
    LocalOfficialProfileManagementSerializer,
    LocalOfficialProfileSelfSerializer,
    LocalOfficialProfileUpdateSerializer,
)
from .services import (
    assign_jurisdiction,
    create_local_official_profile,
    is_effective_local_official,
    revoke_jurisdiction,
    update_local_official_profile,
)


def _profile_queryset():
    return LocalOfficialProfile.objects.select_related("user").order_by("official_id", "id")


def _assignment_queryset(profile):
    return (
        OfficialJurisdictionAssignment.objects.select_related("region", "district", "ward")
        .filter(official=profile)
        .order_by("-starts_at", "-created_at", "id")
    )


def _annotate_effective_assignments(queryset, *, user):
    if not is_effective_local_official(user):
        return queryset.annotate(_effective=Value(False, output_field=BooleanField()))
    now = timezone.now()
    return queryset.annotate(
        _effective=Case(
            When(
                Q(status=OfficialJurisdictionAssignment.Status.ACTIVE)
                & Q(starts_at__lte=now)
                & (Q(expires_at__isnull=True) | Q(expires_at__gt=now)),
                then=Value(True),
            ),
            default=Value(False),
            output_field=BooleanField(),
        )
    )


class ManagementLocalOfficialProfileCollectionView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsManagement]
    pagination_class = LocalOfficialPagination

    def get_serializer_class(self):
        if self.request.method == "POST":
            return LocalOfficialProfileCreateSerializer
        return LocalOfficialProfileManagementSerializer

    @extend_schema(responses={200: LocalOfficialProfileManagementSerializer(many=True)})
    def get(self, request, *args, **kwargs):
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(_profile_queryset(), request, view=self)
        return paginator.get_paginated_response(LocalOfficialProfileManagementSerializer(page, many=True).data)

    @extend_schema(request=LocalOfficialProfileCreateSerializer, responses={201: LocalOfficialProfileManagementSerializer})
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = create_local_official_profile(
            actor=request.user,
            user=serializer.validated_data["user"],
            official_number=serializer.validated_data["official_number"],
            request=request,
        )
        return Response(LocalOfficialProfileManagementSerializer(profile).data, status=status.HTTP_201_CREATED)


class ManagementLocalOfficialProfileDetailView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsManagement]
    http_method_names = ["get", "patch", "head", "options"]

    def get_profile(self, official_id):
        return get_object_or_404(_profile_queryset(), official_id=official_id)

    @extend_schema(responses={200: LocalOfficialProfileManagementSerializer})
    def get(self, request, official_id, *args, **kwargs):
        return Response(LocalOfficialProfileManagementSerializer(self.get_profile(official_id)).data)

    @extend_schema(request=LocalOfficialProfileUpdateSerializer, responses={200: LocalOfficialProfileManagementSerializer})
    def patch(self, request, official_id, *args, **kwargs):
        serializer = LocalOfficialProfileUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        profile = update_local_official_profile(
            actor=request.user,
            profile=self.get_profile(official_id),
            request=request,
            **serializer.validated_data,
        )
        return Response(LocalOfficialProfileManagementSerializer(profile).data)


class ManagementLocalOfficialJurisdictionCollectionView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsManagement]
    pagination_class = LocalOfficialPagination

    def get_profile(self, official_id):
        return get_object_or_404(_profile_queryset(), official_id=official_id)

    @extend_schema(responses={200: JurisdictionAssignmentManagementSerializer(many=True)})
    def get(self, request, official_id, *args, **kwargs):
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(_assignment_queryset(self.get_profile(official_id)), request, view=self)
        return paginator.get_paginated_response(JurisdictionAssignmentManagementSerializer(page, many=True).data)

    @extend_schema(request=JurisdictionAssignmentInputSerializer, responses={201: JurisdictionAssignmentManagementSerializer})
    def post(self, request, official_id, *args, **kwargs):
        serializer = JurisdictionAssignmentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assignment = assign_jurisdiction(
            actor=request.user,
            official=self.get_profile(official_id),
            request=request,
            **serializer.validated_data,
        )
        return Response(JurisdictionAssignmentManagementSerializer(assignment).data, status=status.HTTP_201_CREATED)


class ManagementLocalOfficialJurisdictionRevokeView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsManagement]
    http_method_names = ["post", "options"]

    @extend_schema(request=None, responses={200: JurisdictionAssignmentManagementSerializer})
    def post(self, request, official_id, assignment_id, *args, **kwargs):
        profile = get_object_or_404(_profile_queryset(), official_id=official_id)
        assignment = get_object_or_404(
            _assignment_queryset(profile),
            assignment_id=assignment_id,
        )
        assignment = revoke_jurisdiction(actor=request.user, assignment=assignment, request=request)
        return Response(JurisdictionAssignmentManagementSerializer(assignment).data)


class LocalOfficialSelfProfileView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "options"]

    def get_profile(self, user):
        if not is_effective_local_official(user):
            raise PermissionDenied("You do not have access to the Local Official operational profile.")
        return get_object_or_404(_profile_queryset(), user=user, is_active=True)

    @extend_schema(responses={200: LocalOfficialProfileSelfSerializer})
    def get(self, request, *args, **kwargs):
        return Response(LocalOfficialProfileSelfSerializer(self.get_profile(request.user)).data)


class LocalOfficialSelfJurisdictionView(LocalOfficialSelfProfileView):
    pagination_class = LocalOfficialPagination

    @extend_schema(responses={200: JurisdictionAssignmentSelfSerializer(many=True)})
    def get(self, request, *args, **kwargs):
        profile = self.get_profile(request.user)
        queryset = _annotate_effective_assignments(_assignment_queryset(profile), user=request.user)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(JurisdictionAssignmentSelfSerializer(page, many=True).data)
