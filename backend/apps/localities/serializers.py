from rest_framework import serializers

from .models import District, Locality, Region, Ward


class LocalityMutationSerializer(serializers.Serializer):
    ward = serializers.PrimaryKeyRelatedField(queryset=Ward.objects.all())
    name = serializers.CharField(max_length=150, trim_whitespace=True)
    kind = serializers.ChoiceField(choices=Locality.Kind.choices)


class LocalitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Locality
        fields = ("id", "name", "kind", "approved", "ward")
        read_only_fields = fields


class RegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = ("id", "name")
        read_only_fields = fields


class DistrictSerializer(serializers.ModelSerializer):
    class Meta:
        model = District
        fields = ("id", "name", "region")
        read_only_fields = fields


class WardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ward
        fields = ("id", "name", "district")
        read_only_fields = fields


class LocalityPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Locality
        fields = ("id", "name", "kind", "ward")
        read_only_fields = fields


class RegionFilterSerializer(serializers.Serializer):
    search = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)


class DistrictFilterSerializer(serializers.Serializer):
    region = serializers.UUIDField(required=False)
    search = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)


class WardFilterSerializer(serializers.Serializer):
    district = serializers.UUIDField(required=False)
    search = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)


class LocalityFilterSerializer(serializers.Serializer):
    ward = serializers.UUIDField(required=False)
    kind = serializers.ChoiceField(required=False, choices=Locality.Kind.choices)
    search = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)
