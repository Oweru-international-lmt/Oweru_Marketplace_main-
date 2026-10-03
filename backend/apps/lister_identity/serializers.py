from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .evidence import normalize_evidence_reference
from .models import ListerIdentity


@extend_schema_field(OpenApiTypes.STR)
class OpaqueEvidenceReferenceField(serializers.Field):
    def to_internal_value(self, data):
        return normalize_evidence_reference(data, field_name=self.field_name)

    def to_representation(self, value):
        return value


class ListerIdentityInputSerializer(serializers.Serializer):
    national_id_number = serializers.CharField(max_length=100, required=False, allow_blank=True, trim_whitespace=True)
    national_id_photo_ref = OpaqueEvidenceReferenceField(required=False)
    live_selfie_ref = OpaqueEvidenceReferenceField(required=False)


class ListerIdentityPrivateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListerIdentity
        fields = (
            "id",
            "national_id_number",
            "national_id_photo_ref",
            "live_selfie_ref",
            "status",
            "submitted_at",
            "reviewed_at",
            "review_reason",
            "expires_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ListerIdentityManagementSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source="user.id", read_only=True)
    user_full_name = serializers.CharField(source="user.full_name", read_only=True)
    reviewed_by_id = serializers.UUIDField(source="reviewed_by.id", read_only=True, allow_null=True)

    class Meta:
        model = ListerIdentity
        fields = (
            "id",
            "user_id",
            "user_full_name",
            "national_id_number",
            "national_id_photo_ref",
            "live_selfie_ref",
            "status",
            "submitted_at",
            "reviewed_at",
            "reviewed_by_id",
            "review_reason",
            "expires_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ListerIdentityManagementQueueSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source="user.id", read_only=True)
    user_full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = ListerIdentity
        fields = ("id", "user_id", "user_full_name", "status", "submitted_at", "created_at", "updated_at")
        read_only_fields = fields


class ListerIdentityRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(trim_whitespace=True, allow_blank=False)


class PublicListerProfileSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="user.full_name", read_only=True)
    is_verified = serializers.SerializerMethodField()
    lister_roles = serializers.SerializerMethodField()
    member_since = serializers.DateTimeField(source="user.date_joined", read_only=True)

    class Meta:
        model = ListerIdentity
        fields = ("id", "name", "is_verified", "lister_roles", "member_since")
        read_only_fields = fields

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_verified(self, obj):
        return True

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_lister_roles(self, obj):
        return self.context.get("lister_roles", [])
