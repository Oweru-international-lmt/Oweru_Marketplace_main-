from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.localities.models import Locality
from .models import LocalOfficialProfile, OfficialLocalityCoverage
from .serializers import StrictInputSerializer
from .services import _active_management_actor
from .full_check import assign_locality, revoke_locality, coverage_manager
from apps.verification.pagination import VerificationReviewPagination


class LocalitySerializer(StrictInputSerializer):
    locality = serializers.PrimaryKeyRelatedField(queryset=Locality.objects.filter(approved=True))
    starts_at = serializers.DateTimeField(required=False)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)


class LocalityCoverageView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LocalitySerializer
    pagination_class = VerificationReviewPagination
    def get(self, request, official_id):
        from django.db import transaction
        with transaction.atomic():
            coverage_manager(request.user)
        profile = get_object_or_404(LocalOfficialProfile, official_id=official_id)
        page = self.paginate_queryset(profile.locality_coverage.select_related("locality").order_by("created_at", "id"))
        return self.get_paginated_response([{"id": str(row.pk), "locality_id": str(row.locality_id), "locality": row.locality.name, "starts_at": row.starts_at, "expires_at": row.expires_at, "revoked_at": row.revoked_at} for row in page])
    def post(self, request, official_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = get_object_or_404(LocalOfficialProfile, official_id=official_id)
        row = assign_locality(actor=request.user, official=profile, request=request, **serializer.validated_data)
        return Response({"id": str(row.pk), "locality_id": str(row.locality_id)}, status=201)


class RevokeLocalityView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, official_id, coverage_id):
        serializer = StrictInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = get_object_or_404(OfficialLocalityCoverage, pk=coverage_id, official__official_id=official_id)
        row = revoke_locality(actor=request.user, coverage=row, request=request)
        return Response({"id": str(row.pk), "revoked_at": row.revoked_at})
