from rest_framework import serializers

from apps.media.serializers import MediaSafeSerializer
from apps.properties.serializers import GeoJSONPointField, GeoJSONPolygonField, RejectUnknownFieldsMixin

from .models import SiteCapture


class StrictBooleanField(serializers.BooleanField):
    def to_internal_value(self, data):
        if type(data) is not bool:
            raise serializers.ValidationError("This field must be a boolean.")
        return data


class SiteCapturePrivateSerializer(serializers.ModelSerializer):
    property_id = serializers.CharField(source="property.property_id", read_only=True)
    observed_point = GeoJSONPointField(read_only=True)
    observed_boundary = GeoJSONPolygonField(read_only=True)

    class Meta:
        model = SiteCapture
        fields = (
            "capture_id",
            "property_id",
            "status",
            "captured_at",
            "observed_point",
            "observed_boundary",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class SiteCaptureCreateSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    observed_point = GeoJSONPointField()
    observed_boundary = GeoJSONPolygonField()


class SiteCaptureUpdateSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    observed_point = GeoJSONPointField(required=False)
    observed_boundary = GeoJSONPolygonField()


class EmptySiteCaptureActionSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    pass


class SiteCapturePromotionSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    promote_point = StrictBooleanField(default=True, required=False)
    promote_boundary = StrictBooleanField(default=False, required=False)


class SiteCaptureMediaUploadSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    image = serializers.ImageField()
    captured_at = serializers.DateTimeField(required=False)
    captured_location = GeoJSONPointField(required=False)
    device = serializers.CharField(max_length=255, required=False, allow_blank=True, trim_whitespace=True)


__all__ = [
    "EmptySiteCaptureActionSerializer",
    "MediaSafeSerializer",
    "SiteCaptureCreateSerializer",
    "SiteCaptureMediaUploadSerializer",
    "SiteCapturePrivateSerializer",
    "SiteCapturePromotionSerializer",
    "SiteCaptureUpdateSerializer",
]
