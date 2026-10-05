from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.audit.services import record_sensitive_access
from apps.roles.catalog import ROLE_MANAGEMENT
from apps.roles.services import user_has_role

from .models import ListingPhoto
from .serializers import (
    EmptyActionSerializer,
    ListingCreateSerializer,
    ListingPrivateSerializer,
    ListingPhotoAddSerializer,
    ListingPhotoReorderSerializer,
    ListingPhotoSerializer,
    ListingSuspendSerializer,
    ListingUpdateSerializer,
)
from .services import (
    activate_listing,
    add_listing_photo,
    create_listing,
    get_accessible_listings,
    get_listing,
    remove_listing_photo,
    restore_listing,
    reorder_listing_photos,
    suspend_listing,
    update_listing,
    withdraw_listing,
)


def _management_listing_detail_access(request, listing):
    return listing.lister_id != request.user.pk and user_has_role(request.user, ROLE_MANAGEMENT)


def _record_management_collection_access(request):
    if user_has_role(request.user, ROLE_MANAGEMENT):
        record_sensitive_access(
            actor=request.user,
            entity_type="Listing",
            entity_id="",
            after={
                "access_type": "management_listing_collection",
                "resource": "listing_collection",
            },
            request=request,
        )


def _record_management_detail_access(request, listing):
    if _management_listing_detail_access(request, listing):
        record_sensitive_access(
            actor=request.user,
            entity_type="Listing",
            entity_id=listing.pk,
            after={
                "access_type": "management_listing_detail",
                "listing_id": listing.listing_id,
            },
            request=request,
        )


class ListingCollectionView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ListingPrivateSerializer

    def get_queryset(self):
        return get_accessible_listings(self.request.user)

    @extend_schema(responses={200: ListingPrivateSerializer(many=True)})
    def get(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        _record_management_collection_access(request)
        return Response(serializer.data)

    @extend_schema(request=ListingCreateSerializer, responses={201: ListingPrivateSerializer})
    def post(self, request, *args, **kwargs):
        serializer = ListingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        listing = create_listing(
            actor=request.user,
            property_record=serializer.validated_data["property"],
            lister_kind=serializer.validated_data["lister_kind"],
            selling_price=serializer.validated_data["selling_price"],
            owner_price=serializer.validated_data["owner_price"],
            description=serializer.validated_data.get("description", ""),
            features=serializer.validated_data.get("features"),
            request=request,
        )
        return Response(self.get_serializer(listing).data, status=status.HTTP_201_CREATED)


class ListingDetailView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ListingPrivateSerializer

    @extend_schema(responses={200: ListingPrivateSerializer})
    def get(self, request, listing_id, *args, **kwargs):
        listing = get_listing(actor=request.user, listing_id=listing_id)
        _record_management_detail_access(request, listing)
        return Response(self.get_serializer(listing).data)

    @extend_schema(request=ListingUpdateSerializer, responses={200: ListingPrivateSerializer})
    def patch(self, request, listing_id, *args, **kwargs):
        listing = get_listing(actor=request.user, listing_id=listing_id)
        serializer = ListingUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        listing = update_listing(actor=request.user, listing=listing, request=request, **serializer.validated_data)
        return Response(self.get_serializer(listing).data)


class ListingActivateView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ListingPrivateSerializer

    @extend_schema(request=EmptyActionSerializer, responses={200: ListingPrivateSerializer})
    def post(self, request, listing_id, *args, **kwargs):
        serializer = EmptyActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        listing = get_listing(actor=request.user, listing_id=listing_id)
        listing = activate_listing(actor=request.user, listing=listing, request=request)
        return Response(self.get_serializer(listing).data)


class ListingWithdrawView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ListingPrivateSerializer

    @extend_schema(request=EmptyActionSerializer, responses={200: ListingPrivateSerializer})
    def post(self, request, listing_id, *args, **kwargs):
        serializer = EmptyActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        listing = get_listing(actor=request.user, listing_id=listing_id)
        listing = withdraw_listing(actor=request.user, listing=listing, request=request)
        return Response(self.get_serializer(listing).data)


class ListingPhotoCollectionView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ListingPhotoSerializer
    queryset = ListingPhoto.objects.none()

    @extend_schema(responses={200: ListingPhotoSerializer(many=True)})
    def get(self, request, listing_id, *args, **kwargs):
        listing = get_listing(actor=request.user, listing_id=listing_id)
        photos = listing.photos.select_related("media").order_by("position", "created_at")
        return Response(self.get_serializer(photos, many=True).data)

    @extend_schema(request=ListingPhotoAddSerializer, responses={201: ListingPhotoSerializer})
    def post(self, request, listing_id, *args, **kwargs):
        listing = get_listing(actor=request.user, listing_id=listing_id)
        serializer = ListingPhotoAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        listing_photo = add_listing_photo(
            actor=request.user,
            listing=listing,
            media=serializer.validated_data["media_id"],
            position=serializer.validated_data.get("position"),
            request=request,
        )
        return Response(self.get_serializer(listing_photo).data, status=status.HTTP_201_CREATED)


class ListingPhotoDetailView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ListingPhotoSerializer
    queryset = ListingPhoto.objects.none()

    @extend_schema(responses={204: None})
    def delete(self, request, listing_id, photo_id, *args, **kwargs):
        listing = get_listing(actor=request.user, listing_id=listing_id)
        remove_listing_photo(actor=request.user, listing=listing, listing_photo=photo_id, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ListingPhotoReorderView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ListingPhotoReorderSerializer
    queryset = ListingPhoto.objects.none()

    @extend_schema(request=ListingPhotoReorderSerializer, responses={200: ListingPhotoSerializer(many=True)})
    def post(self, request, listing_id, *args, **kwargs):
        listing = get_listing(actor=request.user, listing_id=listing_id)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        photos = reorder_listing_photos(
            actor=request.user,
            listing=listing,
            ordered_photo_ids=serializer.validated_data["photo_ids"],
            request=request,
        )
        return Response(ListingPhotoSerializer(photos, many=True).data)


class ManagementListingSuspendView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ListingPrivateSerializer

    @extend_schema(request=ListingSuspendSerializer, responses={200: ListingPrivateSerializer})
    def post(self, request, listing_id, *args, **kwargs):
        serializer = ListingSuspendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        listing = get_listing(actor=request.user, listing_id=listing_id)
        listing = suspend_listing(
            actor=request.user,
            listing=listing,
            reason=serializer.validated_data["reason"],
            request=request,
        )
        return Response(self.get_serializer(listing).data)


class ManagementListingRestoreView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ListingPrivateSerializer

    @extend_schema(request=EmptyActionSerializer, responses={200: ListingPrivateSerializer})
    def post(self, request, listing_id, *args, **kwargs):
        serializer = EmptyActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        listing = get_listing(actor=request.user, listing_id=listing_id)
        listing = restore_listing(actor=request.user, listing=listing, request=request)
        return Response(self.get_serializer(listing).data)
