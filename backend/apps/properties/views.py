from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.audit.services import record_sensitive_access
from apps.roles.catalog import ROLE_MANAGEMENT
from apps.roles.services import user_has_role

from .policies import get_accessible_property_records
from .serializers import (
    PropertyRecordCreateSerializer,
    PropertyRecordPrivateSerializer,
    PropertyRecordWriteSerializer,
)
from .services import create_property_record, get_property_record, update_property_record


class PropertyRecordCollectionView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PropertyRecordPrivateSerializer

    def get_queryset(self):
        return get_accessible_property_records(self.request.user)

    @extend_schema(responses={200: PropertyRecordPrivateSerializer(many=True)})
    def get(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return Response(serializer.data)

    @extend_schema(request=PropertyRecordCreateSerializer, responses={201: PropertyRecordPrivateSerializer})
    def post(self, request, *args, **kwargs):
        serializer = PropertyRecordCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        property_record = create_property_record(actor=request.user, request=request, **serializer.validated_data)
        return Response(PropertyRecordPrivateSerializer(property_record).data, status=status.HTTP_201_CREATED)


class PropertyRecordDetailView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PropertyRecordPrivateSerializer

    @extend_schema(responses={200: PropertyRecordPrivateSerializer})
    def get(self, request, property_id, *args, **kwargs):
        property_record = get_property_record(actor=request.user, property_id=property_id)
        if property_record.created_by_id != request.user.pk and user_has_role(request.user, ROLE_MANAGEMENT):
            record_sensitive_access(
                actor=request.user,
                entity_type="PropertyRecord",
                entity_id=property_record.pk,
                after={
                    "access_type": "management_property_detail",
                    "property_id": property_record.property_id,
                },
                request=request,
            )
        return Response(self.get_serializer(property_record).data)

    @extend_schema(request=PropertyRecordWriteSerializer, responses={200: PropertyRecordPrivateSerializer})
    def patch(self, request, property_id, *args, **kwargs):
        property_record = get_property_record(actor=request.user, property_id=property_id)
        serializer = PropertyRecordWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        property_record = update_property_record(
            actor=request.user,
            property_record=property_record,
            request=request,
            **serializer.validated_data,
        )
        return Response(self.get_serializer(property_record).data)
