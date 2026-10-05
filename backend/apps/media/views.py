from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.media.serializers import (
    ImageMediaUploadSerializer,
    MediaAccessRequestSerializer,
    MediaAccessResponseSerializer,
    MediaSafeSerializer,
)
from apps.media.services import create_image_media, get_media, get_media_read_url


class ImageMediaUploadView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = ImageMediaUploadSerializer

    @extend_schema(request=ImageMediaUploadSerializer, responses={201: MediaSafeSerializer})
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        media = create_image_media(actor=request.user, request=request, **serializer.validated_data)
        return Response(MediaSafeSerializer(media).data, status=status.HTTP_201_CREATED)


class MediaAccessView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MediaAccessRequestSerializer

    @extend_schema(parameters=[MediaAccessRequestSerializer], responses={200: MediaAccessResponseSerializer})
    def get(self, request, media_id, *args, **kwargs):
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        media = get_media(actor=request.user, media_id=media_id)
        payload = get_media_read_url(
            actor=request.user,
            media=media,
            variant=serializer.validated_data.get("variant"),
            request=request,
        )
        return Response(MediaAccessResponseSerializer(payload).data)
