from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.accounts.models import User
from apps.localities.models import Region, District
from apps.verification.serializers import StrictInputSerializer
from apps.verification.pagination import VerificationReviewPagination
from .models import ProfessionalProfile
from .services import register_professional, update_professional, require_manager, effective_profile


class ProfessionalSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="user.full_name", read_only=True)
    class Meta:
        model = ProfessionalProfile
        fields = ["id", "name", "professional_type", "registration_number", "status", "regions", "districts", "verified_at", "created_at", "updated_at"]
        read_only_fields = fields


class ProfessionalManagementSerializer(ProfessionalSerializer):
    """PRO-01: the management table also shows contacts, coverage names and who verified them."""
    phone = serializers.CharField(source="user.phone", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)
    national_id = serializers.SerializerMethodField()
    region_names = serializers.SerializerMethodField()
    district_names = serializers.SerializerMethodField()
    verified_by = serializers.CharField(source="verified_by.full_name", read_only=True)
    class Meta(ProfessionalSerializer.Meta):
        fields = ProfessionalSerializer.Meta.fields + ["phone", "email", "national_id", "region_names", "district_names", "verified_by"]
        read_only_fields = fields
    def get_national_id(self, obj):
        value = obj.national_id_number or ""
        return "•" * max(0, len(value) - 4) + value[-4:]
    def get_region_names(self, obj):
        return [item.name for item in obj.regions.all()]
    def get_district_names(self, obj):
        return [item.name for item in obj.districts.all()]


class RegistrationSerializer(StrictInputSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False)
    email = serializers.EmailField(required=False)
    phone = serializers.CharField(max_length=30, required=False)
    full_name = serializers.CharField(max_length=255, required=False)
    professional_type = serializers.ChoiceField(choices=ProfessionalProfile.Type.choices)
    registration_number = serializers.CharField(max_length=100)
    national_id_number = serializers.CharField(max_length=100)
    regions = serializers.PrimaryKeyRelatedField(queryset=Region.objects.all(), many=True, required=False)
    districts = serializers.PrimaryKeyRelatedField(queryset=District.objects.all(), many=True, required=False)


class UpdateSerializer(StrictInputSerializer):
    status = serializers.ChoiceField(choices=["ACTIVE", "INACTIVE"], required=False)
    reason = serializers.CharField(max_length=1000, required=False)
    registration_number = serializers.CharField(max_length=100, required=False)
    regions = serializers.PrimaryKeyRelatedField(queryset=Region.objects.all(), many=True, required=False)
    districts = serializers.PrimaryKeyRelatedField(queryset=District.objects.all(), many=True, required=False)


class ProfessionalCollectionView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RegistrationSerializer
    pagination_class = VerificationReviewPagination
    def get(self, request):
        require_manager(request.user)
        queryset = ProfessionalProfile.objects.select_related("user", "verified_by").prefetch_related("regions", "districts").order_by("registration_number")
        return self.get_paginated_response(ProfessionalManagementSerializer(self.paginate_queryset(queryset), many=True).data)
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from django.core.exceptions import ValidationError as DjangoValidationError
        from rest_framework.exceptions import ValidationError
        try:
            profile = register_professional(actor=request.user, request=request, **serializer.validated_data)
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict) from exc
        return Response(ProfessionalManagementSerializer(profile).data, status=201)


class ProfessionalDetailView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UpdateSerializer
    def get(self, request, profile_id):
        require_manager(request.user)
        return Response(ProfessionalManagementSerializer(get_object_or_404(ProfessionalProfile, pk=profile_id)).data)
    def patch(self, request, profile_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = update_professional(actor=request.user, profile_id=profile_id, request=request, **serializer.validated_data)
        return Response(ProfessionalManagementSerializer(profile).data)


class ProfessionalSelfView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProfessionalSerializer
    def get(self, request):
        from rest_framework.exceptions import PermissionDenied
        profile = effective_profile(request.user)
        if profile is None:
            raise PermissionDenied("An active professional account is required.")
        return Response(self.get_serializer(profile).data)
