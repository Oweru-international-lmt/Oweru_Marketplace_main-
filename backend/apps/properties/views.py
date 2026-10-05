from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.audit.services import record_sensitive_access
from apps.roles.permissions import IsManagement
from apps.roles.catalog import ROLE_MANAGEMENT
from apps.roles.services import user_has_role

from .duplicate_services import confirm_possible_duplicate, dismiss_possible_duplicate
from .models import PossibleDuplicate
from .policies import get_accessible_property_records
from .serializers import (
    EmptyDuplicateReviewActionSerializer,
    PossibleDuplicateReviewSerializer,
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


class ManagementPossibleDuplicateCollectionView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsManagement]
    serializer_class = PossibleDuplicateReviewSerializer

    def get_queryset(self):
        queryset = PossibleDuplicate.objects.select_related(
            "property_a__region",
            "property_a__district",
            "property_a__ward",
            "property_a__locality",
            "property_b__region",
            "property_b__district",
            "property_b__ward",
            "property_b__locality",
            "reviewed_by",
        ).order_by("created_at", "id")
        requested_status = self.request.query_params.get("status")
        if requested_status is None or requested_status == "":
            return queryset.filter(status=PossibleDuplicate.Status.PENDING)
        allowed = {choice.value for choice in PossibleDuplicate.Status}
        if requested_status not in allowed:
            raise ValidationError({"status": "Unsupported duplicate status filter."})
        return queryset.filter(status=requested_status)

    @extend_schema(responses={200: PossibleDuplicateReviewSerializer(many=True)})
    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(self.get_queryset(), many=True).data)


class ManagementPossibleDuplicateDetailView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsManagement]
    serializer_class = PossibleDuplicateReviewSerializer

    def get_queryset(self):
        return PossibleDuplicate.objects.select_related(
            "property_a__region",
            "property_a__district",
            "property_a__ward",
            "property_a__locality",
            "property_b__region",
            "property_b__district",
            "property_b__ward",
            "property_b__locality",
            "reviewed_by",
        )

    def get_duplicate(self, duplicate_id):
        try:
            return self.get_queryset().get(pk=duplicate_id)
        except (TypeError, ValueError, PossibleDuplicate.DoesNotExist) as exc:
            raise NotFound("Possible duplicate was not found.") from exc

    @extend_schema(responses={200: PossibleDuplicateReviewSerializer})
    def get(self, request, duplicate_id, *args, **kwargs):
        return Response(self.get_serializer(self.get_duplicate(duplicate_id)).data)


class ManagementPossibleDuplicateConfirmView(ManagementPossibleDuplicateDetailView):
    http_method_names = ["post", "options"]
    serializer_class = PossibleDuplicateReviewSerializer

    @extend_schema(request=EmptyDuplicateReviewActionSerializer, responses={200: PossibleDuplicateReviewSerializer})
    def post(self, request, duplicate_id, *args, **kwargs):
        action_serializer = EmptyDuplicateReviewActionSerializer(data=request.data)
        action_serializer.is_valid(raise_exception=True)
        reviewed = confirm_possible_duplicate(
            actor=request.user,
            possible_duplicate=self.get_duplicate(duplicate_id),
            request=request,
        )
        return Response(self.get_serializer(reviewed).data)


class ManagementPossibleDuplicateDismissView(ManagementPossibleDuplicateDetailView):
    http_method_names = ["post", "options"]
    serializer_class = PossibleDuplicateReviewSerializer

    @extend_schema(request=EmptyDuplicateReviewActionSerializer, responses={200: PossibleDuplicateReviewSerializer})
    def post(self, request, duplicate_id, *args, **kwargs):
        action_serializer = EmptyDuplicateReviewActionSerializer(data=request.data)
        action_serializer.is_valid(raise_exception=True)
        reviewed = dismiss_possible_duplicate(
            actor=request.user,
            possible_duplicate=self.get_duplicate(duplicate_id),
            request=request,
        )
        return Response(self.get_serializer(reviewed).data)
