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
    map_context = serializers.SerializerMethodField()
    assets = serializers.SerializerMethodField()

    def get_map_context(self, obj):
        return {"provider": "OPENSTREETMAP", "tile_url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png", "attribution": "© OpenStreetMap contributors", "satellite_available": False, "ownership_disclaimer": "Maps do not prove ownership."}

    def get_assets(self, obj):
        return [{"media_id": row.media.media_id, "source": row.source, "flags": row.flags, "distance_m": str(row.distance_m) if row.distance_m is not None else None} for row in obj.assets.select_related("media")]

    class Meta:
        model = SiteCapture
        fields = (
            "capture_id",
            "property_id",
            "status",
            "captured_at",
            "observed_point",
            "observed_boundary",
            "measured_area_sqm", "area_difference_percent", "review_flags", "overlap_findings", "map_context", "assets",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class SiteCaptureCreateSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    verification_task_id = serializers.UUIDField(required=False)
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


class CaptureCornerInputSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    point = GeoJSONPointField()
    accuracy_m = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    observed_at = serializers.DateTimeField()
    device = serializers.CharField(max_length=255)


__all__ = [
    "EmptySiteCaptureActionSerializer",
    "MediaSafeSerializer",
    "SiteCaptureCreateSerializer",
    "SiteCaptureMediaUploadSerializer",
    "SiteCapturePrivateSerializer",
    "SiteCapturePromotionSerializer",
    "SiteCaptureUpdateSerializer",
]
