from collections.abc import Mapping

from django.contrib.gis.geos import GEOSException, Point, Polygon
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.localities.models import District, Locality, Region, Ward

from .models import PossibleDuplicate, PropertyRecord


class RejectUnknownFieldsMixin:
    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError("Expected an object.")
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({field: "This field is not supported." for field in sorted(unknown)})
        return super().to_internal_value(data)


def _validate_coordinate_pair(value):
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 2
        or isinstance(value[0], bool)
        or isinstance(value[1], bool)
    ):
        raise serializers.ValidationError("Coordinates must be [longitude, latitude].")
    try:
        longitude = float(value[0])
        latitude = float(value[1])
    except (TypeError, ValueError) as exc:
        raise serializers.ValidationError("Coordinates must be numeric.") from exc
    if not -180 <= longitude <= 180:
        raise serializers.ValidationError("Longitude must be between -180 and 180.")
    if not -90 <= latitude <= 90:
        raise serializers.ValidationError("Latitude must be between -90 and 90.")
    return longitude, latitude


@extend_schema_field(OpenApiTypes.OBJECT)
class GeoJSONPointField(serializers.Field):
    default_error_messages = {
        "invalid": "Point must use GeoJSON format with type Point and [longitude, latitude] coordinates."
    }

    def to_internal_value(self, data):
        if not isinstance(data, Mapping) or data.get("type") != "Point":
            self.fail("invalid")
        longitude, latitude = _validate_coordinate_pair(data.get("coordinates"))
        return Point(longitude, latitude, srid=4326)

    def to_representation(self, value):
        if value is None:
            return None
        return {"type": "Point", "coordinates": [value.x, value.y]}


@extend_schema_field(OpenApiTypes.OBJECT)
class GeoJSONPolygonField(serializers.Field):
    default_error_messages = {
        "invalid": "Boundary must use GeoJSON format with type Polygon and valid linear-ring coordinates."
    }

    def __init__(self, **kwargs):
        kwargs.setdefault("allow_null", True)
        kwargs.setdefault("required", False)
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        if data is None:
            return None
        if not isinstance(data, Mapping) or data.get("type") != "Polygon":
            self.fail("invalid")
        coordinates = data.get("coordinates")
        if not isinstance(coordinates, list) or not coordinates:
            self.fail("invalid")

        rings = []
        for ring in coordinates:
            if not isinstance(ring, list) or len(ring) < 4:
                self.fail("invalid")
            parsed_ring = [_validate_coordinate_pair(pair) for pair in ring]
            if parsed_ring[0] != parsed_ring[-1]:
                raise serializers.ValidationError("Polygon rings must be closed.")
            rings.append(parsed_ring)

        try:
            polygon = Polygon(*rings, srid=4326)
        except (GEOSException, TypeError, ValueError) as exc:
            raise serializers.ValidationError("Boundary polygon is invalid.") from exc
        if not polygon.valid:
            raise serializers.ValidationError("Boundary polygon is invalid.")
        return polygon

    def to_representation(self, value):
        if value is None:
            return None
        return {"type": "Polygon", "coordinates": [[list(pair) for pair in ring] for ring in value.coords]}


class LocalityReferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Locality
        fields = ("id", "name", "kind", "approved", "ward")
        read_only_fields = fields


class PropertyRecordWriteSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    category = serializers.ChoiceField(choices=PropertyRecord.Category.choices, required=False)
    pin = GeoJSONPointField(required=False)
    boundary = GeoJSONPolygonField()
    region = serializers.PrimaryKeyRelatedField(queryset=Region.objects.all(), required=False)
    district = serializers.PrimaryKeyRelatedField(queryset=District.objects.all(), required=False)
    ward = serializers.PrimaryKeyRelatedField(queryset=Ward.objects.all(), required=False)
    locality = serializers.PrimaryKeyRelatedField(queryset=Locality.objects.all(), required=False)
    locality_name = serializers.CharField(max_length=150, required=False, trim_whitespace=True, allow_blank=False)
    locality_kind = serializers.ChoiceField(choices=Locality.Kind.choices, required=False)
    stated_size = serializers.DecimalField(max_digits=18, decimal_places=2, required=False)
    size_unit = serializers.CharField(max_length=20, required=False, trim_whitespace=True, allow_blank=False)
    title_type = serializers.ChoiceField(choices=PropertyRecord.TitleType.choices, required=False)


class PropertyRecordCreateSerializer(PropertyRecordWriteSerializer):
    category = serializers.ChoiceField(choices=PropertyRecord.Category.choices)
    pin = GeoJSONPointField()
    region = serializers.PrimaryKeyRelatedField(queryset=Region.objects.all())
    district = serializers.PrimaryKeyRelatedField(queryset=District.objects.all())
    ward = serializers.PrimaryKeyRelatedField(queryset=Ward.objects.all())
    stated_size = serializers.DecimalField(max_digits=18, decimal_places=2)
    size_unit = serializers.CharField(max_length=20, trim_whitespace=True, allow_blank=False)
    title_type = serializers.ChoiceField(choices=PropertyRecord.TitleType.choices)


class PropertyRecordPrivateSerializer(serializers.ModelSerializer):
    pin = GeoJSONPointField(read_only=True)
    boundary = GeoJSONPolygonField(read_only=True)
    locality = LocalityReferenceSerializer(read_only=True)

    class Meta:
        model = PropertyRecord
        fields = (
            "property_id",
            "category",
            "pin",
            "boundary",
            "region",
            "district",
            "ward",
            "locality",
            "stated_size",
            "size_unit",
            "title_type",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class EmptyDuplicateReviewActionSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    pass


class DuplicatePropertySummarySerializer(serializers.ModelSerializer):
    region = serializers.CharField(source="region.name", read_only=True)
    district = serializers.CharField(source="district.name", read_only=True)
    ward = serializers.CharField(source="ward.name", read_only=True)
    locality = serializers.CharField(source="locality.name", read_only=True)
    locality_kind = serializers.CharField(source="locality.kind", read_only=True)

    class Meta:
        model = PropertyRecord
        fields = (
            "property_id",
            "category",
            "region",
            "district",
            "ward",
            "locality",
            "locality_kind",
            "stated_size",
            "size_unit",
            "title_type",
        )
        read_only_fields = fields


class PossibleDuplicateReviewSerializer(serializers.ModelSerializer):
    property_a = DuplicatePropertySummarySerializer(read_only=True)
    property_b = DuplicatePropertySummarySerializer(read_only=True)
    reviewed_by = serializers.SerializerMethodField()

    class Meta:
        model = PossibleDuplicate
        fields = (
            "id",
            "status",
            "signals",
            "distance_meters",
            "size_difference_percent",
            "created_at",
            "reviewed_at",
            "reviewed_by",
            "property_a",
            "property_b",
        )
        read_only_fields = fields

    @extend_schema_field(OpenApiTypes.UUID)
    def get_reviewed_by(self, obj):
        if not obj.reviewed_by_id:
            return None
        return str(obj.reviewed_by_id)
