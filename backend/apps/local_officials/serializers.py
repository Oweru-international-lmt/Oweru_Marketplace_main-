from collections.abc import Mapping

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import User
from apps.localities.models import District, Region, Ward

from .models import LocalOfficialProfile, OfficialJurisdictionAssignment


class StrictInputSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError({
                    field: "This field is not allowed." for field in sorted(unknown)
                })
        return super().to_internal_value(data)


class LocalOfficialProfileCreateSerializer(StrictInputSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    official_number = serializers.CharField(max_length=100, trim_whitespace=True)


class LocalOfficialProfileUpdateSerializer(StrictInputSerializer):
    official_number = serializers.CharField(max_length=100, trim_whitespace=True, required=False)
    is_active = serializers.BooleanField(required=False)


class LocalOfficialProfileManagementSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source="user.id", read_only=True)

    class Meta:
        model = LocalOfficialProfile
        fields = (
            "official_id",
            "user_id",
            "official_number",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class LocalOfficialProfileSelfSerializer(serializers.ModelSerializer):
    class Meta:
        model = LocalOfficialProfile
        fields = ("official_id", "official_number", "is_active")
        read_only_fields = fields


class JurisdictionAssignmentInputSerializer(StrictInputSerializer):
    scope_type = serializers.ChoiceField(choices=OfficialJurisdictionAssignment.ScopeType.choices)
    region = serializers.PrimaryKeyRelatedField(queryset=Region.objects.all(), required=False, allow_null=True)
    district = serializers.PrimaryKeyRelatedField(queryset=District.objects.all(), required=False, allow_null=True)
    ward = serializers.PrimaryKeyRelatedField(queryset=Ward.objects.all(), required=False, allow_null=True)
    starts_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField(required=False, allow_null=True)


class AdministrativeAreaSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)


class JurisdictionAssignmentManagementSerializer(serializers.ModelSerializer):
    area = serializers.SerializerMethodField()

    class Meta:
        model = OfficialJurisdictionAssignment
        fields = (
            "assignment_id",
            "scope_type",
            "area",
            "starts_at",
            "expires_at",
            "status",
            "created_at",
            "revoked_at",
        )
        read_only_fields = fields

    @extend_schema_field(AdministrativeAreaSerializer)
    def get_area(self, obj):
        if obj.scope_type == OfficialJurisdictionAssignment.ScopeType.REGION:
            return AdministrativeAreaSerializer(obj.region).data
        if obj.scope_type == OfficialJurisdictionAssignment.ScopeType.DISTRICT:
            return AdministrativeAreaSerializer(obj.district).data
        return AdministrativeAreaSerializer(obj.ward).data


class JurisdictionAssignmentSelfSerializer(JurisdictionAssignmentManagementSerializer):
    effective = serializers.BooleanField(source="_effective", read_only=True)

    class Meta(JurisdictionAssignmentManagementSerializer.Meta):
        fields = JurisdictionAssignmentManagementSerializer.Meta.fields + ("effective",)
        read_only_fields = fields
