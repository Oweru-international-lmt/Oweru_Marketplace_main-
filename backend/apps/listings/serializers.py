from collections.abc import Mapping

from rest_framework import serializers

from apps.media.models import Media
from apps.properties.models import PropertyRecord

from .models import Listing, ListingPhoto


class RejectUnknownFieldsMixin:
    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError("Expected an object.")
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({field: "This field is not supported." for field in sorted(unknown)})
        return super().to_internal_value(data)


class ListingCreateSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    property = serializers.SlugRelatedField(queryset=PropertyRecord.objects.all(), slug_field="property_id")
    lister_kind = serializers.ChoiceField(choices=Listing.ListerKind.choices)
    selling_price = serializers.DecimalField(max_digits=18, decimal_places=0)
    owner_price = serializers.DecimalField(max_digits=18, decimal_places=0)
    description = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)
    features = serializers.JSONField(required=False)


class ListingUpdateSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    selling_price = serializers.DecimalField(max_digits=18, decimal_places=0, required=False)
    owner_price = serializers.DecimalField(max_digits=18, decimal_places=0, required=False)
    description = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)
    features = serializers.JSONField(required=False)


class ListingPrivateSerializer(serializers.ModelSerializer):
    property_id = serializers.CharField(source="property.property_id", read_only=True)

    class Meta:
        model = Listing
        fields = (
            "listing_id",
            "property_id",
            "lister_kind",
            "selling_price",
            "owner_price",
            "currency",
            "status",
            "description",
            "features",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class EmptyActionSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    pass


class ListingSuspendSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    reason = serializers.CharField(trim_whitespace=True, allow_blank=False)


class ListingPhotoSerializer(serializers.ModelSerializer):
    media_id = serializers.CharField(source="media.media_id", read_only=True)

    class Meta:
        model = ListingPhoto
        fields = ("id", "media_id", "position", "created_at")
        read_only_fields = fields


class ListingPhotoAddSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    media_id = serializers.SlugRelatedField(queryset=Media.objects.all(), slug_field="media_id")
    position = serializers.IntegerField(required=False, min_value=0)


class ListingPhotoReorderSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    photo_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=True)
