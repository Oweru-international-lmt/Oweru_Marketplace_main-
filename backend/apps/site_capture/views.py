from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.media.serializers import MediaSafeSerializer
from apps.properties.services import get_property_record

from .models import SiteCapture
from .pagination import SiteCapturePagination
from .serializers import (
    EmptySiteCaptureActionSerializer,
    SiteCaptureCreateSerializer,
    SiteCaptureMediaUploadSerializer,
    SiteCapturePrivateSerializer,
    SiteCapturePromotionSerializer,
    SiteCaptureUpdateSerializer,
)
from .services import (
    create_site_capture,
    get_property_site_captures,
    get_site_capture,
    promote_site_capture,
    remove_site_capture_media,
    submit_site_capture,
    update_site_capture,
    record_corner,
    upload_site_capture_image,
)


class PropertySiteCaptureCollectionView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SiteCapturePrivateSerializer
    pagination_class = SiteCapturePagination
    queryset = SiteCapture.objects.none()
    http_method_names = ["get", "post", "options"]

    def get_property_record(self):
        from django.shortcuts import get_object_or_404
        from apps.properties.models import PropertyRecord
        from .services import _ensure_can_capture
        property_record = get_object_or_404(PropertyRecord, property_id=self.kwargs["property_id"])
        _ensure_can_capture(self.request.user, property_record)
        return property_record

    @extend_schema(responses={200: SiteCapturePrivateSerializer(many=True)})
    def get(self, request, *args, **kwargs):
        property_record = self.get_property_record()
        queryset = get_property_site_captures(actor=request.user, property_record=property_record)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = self.get_serializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(request=SiteCaptureCreateSerializer, responses={201: SiteCapturePrivateSerializer})
    def post(self, request, *args, **kwargs):
        serializer = SiteCaptureCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        site_capture = create_site_capture(
            property_record=self.get_property_record(),
            actor=request.user,
            request=request,
            **serializer.validated_data,
        )
        return Response(SiteCapturePrivateSerializer(site_capture).data, status=status.HTTP_201_CREATED)


class SiteCaptureDetailView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SiteCapturePrivateSerializer
    http_method_names = ["get", "patch", "options"]

    def get_site_capture(self):
        return get_site_capture(actor=self.request.user, capture_id=self.kwargs["capture_id"])

    @extend_schema(responses={200: SiteCapturePrivateSerializer})
    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(self.get_site_capture()).data)

    @extend_schema(request=SiteCaptureUpdateSerializer, responses={200: SiteCapturePrivateSerializer})
    def patch(self, request, *args, **kwargs):
        serializer = SiteCaptureUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        site_capture = update_site_capture(
            site_capture=self.get_site_capture(),
            actor=request.user,
            request=request,
            **serializer.validated_data,
        )
        return Response(self.get_serializer(site_capture).data)


class SiteCaptureSubmitView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SiteCapturePrivateSerializer
    http_method_names = ["post", "options"]

    @extend_schema(request=EmptySiteCaptureActionSerializer, responses={200: SiteCapturePrivateSerializer})
    def post(self, request, capture_id, *args, **kwargs):
        action_serializer = EmptySiteCaptureActionSerializer(data=request.data)
        action_serializer.is_valid(raise_exception=True)
        site_capture = submit_site_capture(
            site_capture=get_site_capture(actor=request.user, capture_id=capture_id),
            actor=request.user,
            request=request,
        )
        return Response(SiteCapturePrivateSerializer(site_capture).data)


class SiteCapturePromoteView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SiteCapturePrivateSerializer
    http_method_names = ["post", "options"]

    @extend_schema(request=SiteCapturePromotionSerializer, responses={200: SiteCapturePrivateSerializer})
    def post(self, request, capture_id, *args, **kwargs):
        serializer = SiteCapturePromotionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        site_capture = get_site_capture(actor=request.user, capture_id=capture_id)
        promote_site_capture(
            site_capture=site_capture,
            actor=request.user,
            request=request,
            **serializer.validated_data,
        )
        return Response(SiteCapturePrivateSerializer(site_capture).data)


class SiteCaptureMediaCollectionView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SiteCaptureMediaUploadSerializer
    parser_classes = [MultiPartParser, FormParser]
    http_method_names = ["post", "options"]

    @extend_schema(request=SiteCaptureMediaUploadSerializer, responses={201: MediaSafeSerializer})
    def post(self, request, capture_id, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        media = upload_site_capture_image(
            site_capture=get_site_capture(actor=request.user, capture_id=capture_id),
            actor=request.user,
            request=request,
            **serializer.validated_data,
        )
        return Response(MediaSafeSerializer(media).data, status=status.HTTP_201_CREATED)


class SiteCaptureMediaDetailView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = EmptySiteCaptureActionSerializer
    http_method_names = ["delete", "options"]

    @extend_schema(responses={204: None})
    def delete(self, request, capture_id, media_id, *args, **kwargs):
        action_serializer = self.get_serializer(data=request.data)
        action_serializer.is_valid(raise_exception=True)
        remove_site_capture_media(
            site_capture=get_site_capture(actor=request.user, capture_id=capture_id),
            media=media_id,
            actor=request.user,
            request=request,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class SiteCaptureCornerView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, capture_id):
        from .serializers import CaptureCornerInputSerializer
        from django.shortcuts import get_object_or_404
        serializer = CaptureCornerInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        corner = record_corner(actor=request.user, site_capture=get_object_or_404(SiteCapture, capture_id=capture_id), request=request, **serializer.validated_data)
        return Response({"id": str(corner.pk), "sequence": corner.sequence, "accuracy_m": str(corner.accuracy_m)}, status=201)
