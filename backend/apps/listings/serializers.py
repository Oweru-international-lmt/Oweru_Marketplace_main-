from collections.abc import Mapping

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.lister_identity.models import ListerIdentity
from apps.lister_identity.services import get_public_verification_summary
from apps.media.models import Media
from apps.properties.models import PropertyRecord

from . import services
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


class PublicLocalityHierarchySerializer(serializers.Serializer):
    region = serializers.CharField(source="region.name", read_only=True)
    district = serializers.CharField(source="district.name", read_only=True)
    ward = serializers.CharField(source="ward.name", read_only=True)
    locality = serializers.CharField(source="locality.name", read_only=True)
    locality_kind = serializers.CharField(source="locality.kind", read_only=True)


class PropertyRecordPublicSerializer(serializers.ModelSerializer):
    location = PublicLocalityHierarchySerializer(source="*", read_only=True)

    class Meta:
        model = PropertyRecord
        fields = (
            "property_id",
            "category",
            "stated_size",
            "size_unit",
            "title_type",
            "location",
        )
        read_only_fields = fields


class ListingPublicVerificationSerializer(serializers.Serializer):
    level = serializers.IntegerField()
    label = serializers.CharField()
    is_verified = serializers.BooleanField()


class ListingPublicListerSerializer(serializers.Serializer):
    display_name = serializers.CharField(source="lister.full_name", read_only=True)
    lister_kind = serializers.CharField(read_only=True)
    verification = serializers.SerializerMethodField()
    member_since = serializers.DateTimeField(source="lister.date_joined", read_only=True)

    @extend_schema_field(ListingPublicVerificationSerializer)
    def get_verification(self, obj):
        try:
            identity = obj.lister.lister_identity
        except ListerIdentity.DoesNotExist:
            identity = None
        return get_public_verification_summary(
            user=obj.lister,
            identity=identity,
            property_record=obj.property,
            listing=obj,
        )


class ListingPublicPhotoSerializer(serializers.Serializer):
    position = serializers.IntegerField()
    url = serializers.CharField()


class ListingPublicSerializer(serializers.ModelSerializer):
    property = PropertyRecordPublicSerializer(read_only=True)
    lister = ListingPublicListerSerializer(source="*", read_only=True)
    photos = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = (
            "listing_id",
            "selling_price",
            "currency",
            "status",
            "description",
            "features",
            "created_at",
            "property",
            "lister",
            "photos",
        )
        read_only_fields = fields

    @extend_schema_field(ListingPublicPhotoSerializer(many=True))
    def get_photos(self, obj):
        return services.get_public_listing_photo_display_accesses(listing=obj)


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
