from django.contrib.gis.geos import MultiPolygon
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from apps.leads.policies import authorize, management
from apps.audit.services import create_audit_log
from apps.properties.serializers import GeoJSONPolygonField, RejectUnknownFieldsMixin
from .models import SiteCapture, PublicMapLayer
from .evidence import upload_capture_asset


class AssetInput(RejectUnknownFieldsMixin, serializers.Serializer):
    file = serializers.FileField()
    source = serializers.ChoiceField(choices=["CAMERA", "UPLOAD"])
    device = serializers.CharField(max_length=255, required=False, allow_blank=True)


class CaptureAssetView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = AssetInput

    def post(self, request, capture_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        asset = upload_capture_asset(actor=request.user, site_capture=get_object_or_404(SiteCapture, capture_id=capture_id), request=request, **serializer.validated_data)
        return Response({"media_id": asset.media.media_id, "source": asset.source, "flags": asset.flags, "distance_m": str(asset.distance_m) if asset.distance_m is not None else None}, status=201)


class LayerInput(RejectUnknownFieldsMixin, serializers.Serializer):
    name = serializers.CharField(max_length=200)
    source_reference = serializers.CharField(max_length=1000)
    boundary = GeoJSONPolygonField()

    def validate_boundary(self, value):
        if value is None:
            raise serializers.ValidationError("A public layer polygon is required.")
        return value


class PublicMapLayerView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LayerInput

    @transaction.atomic
    def post(self, request):
        actor = authorize(request.user, "settings.manage")
        if not management(actor):
            raise PermissionDenied("Only authorized Management may load public map layers.")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        values["boundary"] = MultiPolygon(values["boundary"], srid=4326)
        row = PublicMapLayer(loaded_by=actor, **values)
        row.full_clean()
        row.save()
        create_audit_log(actor=actor, action="site_capture.public_layer_loaded", entity_type="PublicMapLayer", entity_id=row.pk, before={}, after={"name": row.name, "source_reference": row.source_reference}, request=request)
        return Response({"id": str(row.pk), "name": row.name}, status=201)
