from django.db.models.functions import Lower
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.roles.permissions import IsManagement

from .models import District, Locality, Region, Ward
from .serializers import (
    DistrictFilterSerializer,
    DistrictSerializer,
    LocalityFilterSerializer,
    LocalityMutationSerializer,
    LocalityPublicSerializer,
    LocalitySerializer,
    RegionFilterSerializer,
    RegionSerializer,
    WardFilterSerializer,
    WardSerializer,
)
from .services import approve_locality, create_locality


def _validated_query(serializer_class, request):
    serializer = serializer_class(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


class RegionListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = RegionSerializer

    @extend_schema(
        parameters=[OpenApiParameter("search", str, OpenApiParameter.QUERY, required=False)],
        responses={200: RegionSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        filters = _validated_query(RegionFilterSerializer, self.request)
        queryset = Region.objects.all()
        if search := filters.get("search"):
            queryset = queryset.filter(name__icontains=search)
        return queryset.order_by(Lower("name"), "id")


class RegionDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    queryset = Region.objects.all()
    serializer_class = RegionSerializer


class DistrictListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = DistrictSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter("region", str, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("search", str, OpenApiParameter.QUERY, required=False),
        ],
        responses={200: DistrictSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        filters = _validated_query(DistrictFilterSerializer, self.request)
        queryset = District.objects.select_related("region")
        if region := filters.get("region"):
            queryset = queryset.filter(region_id=region)
        if search := filters.get("search"):
            queryset = queryset.filter(name__icontains=search)
        return queryset.order_by(Lower("name"), "id")


class DistrictDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    queryset = District.objects.select_related("region")
    serializer_class = DistrictSerializer


class WardListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = WardSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter("district", str, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("search", str, OpenApiParameter.QUERY, required=False),
        ],
        responses={200: WardSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        filters = _validated_query(WardFilterSerializer, self.request)
        queryset = Ward.objects.select_related("district", "district__region")
        if district := filters.get("district"):
            queryset = queryset.filter(district_id=district)
        if search := filters.get("search"):
            queryset = queryset.filter(name__icontains=search)
        return queryset.order_by(Lower("name"), "id")


class WardDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    queryset = Ward.objects.select_related("district", "district__region")
    serializer_class = WardSerializer


class LocalityCollectionView(generics.ListAPIView):
    serializer_class = LocalityPublicSerializer

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [AllowAny()]
        return [IsAuthenticated(), IsManagement()]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return LocalitySerializer
        return LocalityPublicSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter("ward", str, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("kind", str, OpenApiParameter.QUERY, required=False, enum=[choice.value for choice in Locality.Kind]),
            OpenApiParameter("search", str, OpenApiParameter.QUERY, required=False),
        ],
        responses={200: LocalityPublicSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        filters = _validated_query(LocalityFilterSerializer, self.request)
        queryset = Locality.objects.select_related("ward", "ward__district", "ward__district__region").filter(
            approved=True
        )
        if ward := filters.get("ward"):
            queryset = queryset.filter(ward_id=ward)
        if kind := filters.get("kind"):
            queryset = queryset.filter(kind=kind)
        if search := filters.get("search"):
            queryset = queryset.filter(name__icontains=search)
        return queryset.order_by(Lower("name"), "id")

    @extend_schema(request=LocalityMutationSerializer, responses={201: LocalitySerializer})
    def post(self, request, *args, **kwargs):
        serializer = LocalityMutationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        locality = create_locality(
            actor=request.user,
            ward=serializer.validated_data["ward"],
            name=serializer.validated_data["name"],
            kind=serializer.validated_data["kind"],
            request=request,
        )
        return Response(LocalitySerializer(locality).data, status=status.HTTP_201_CREATED)


class LocalityDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    queryset = Locality.objects.select_related("ward", "ward__district", "ward__district__region").filter(approved=True)
    serializer_class = LocalityPublicSerializer


class LocalityApproveView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsManagement]

    @extend_schema(request=None, responses={200: LocalitySerializer})
    def post(self, request, pk, *args, **kwargs):
        locality = get_object_or_404(Locality, pk=pk)
        locality = approve_locality(locality=locality, approved_by=request.user, request=request)
        return Response(LocalitySerializer(locality).data)
