from collections.abc import Mapping

from rest_framework import serializers

from apps.media.models import Media, MediaVariant


class RejectUnknownFieldsMixin:
    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError("Expected an object.")
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({field: "This field is not supported." for field in sorted(unknown)})
        return super().to_internal_value(data)


class ImageMediaUploadSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    image = serializers.ImageField()
    owner_type = serializers.ChoiceField(choices=(("listing", "Listing"), ("property_record", "Property record")))
    owner_id = serializers.CharField()
    source = serializers.ChoiceField(choices=Media.Source.choices, default=Media.Source.UPLOAD, required=False)


class MediaVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = MediaVariant
        fields = ("kind", "mime_type", "size_bytes", "width", "height")
        read_only_fields = fields


class MediaSafeSerializer(serializers.ModelSerializer):
    variants = MediaVariantSerializer(many=True, read_only=True)

    class Meta:
        model = Media
        fields = ("media_id", "source", "mime_type", "size_bytes", "created_at", "variants")
        read_only_fields = fields


class MediaAccessRequestSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    variant = serializers.ChoiceField(choices=MediaVariant.Kind.choices, default=MediaVariant.Kind.DISPLAY, required=False)


class MediaAccessResponseSerializer(serializers.Serializer):
    media_id = serializers.CharField()
    variant = serializers.ChoiceField(choices=MediaVariant.Kind.choices)
    url = serializers.CharField()
    expires_in = serializers.IntegerField()
