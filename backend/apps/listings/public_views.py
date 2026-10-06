from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import generics, serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from . import public_analytics
from .public_search import PublicListingSearchParamsSerializer, get_public_listing_search_queryset, paginate_public_listings
from .serializers import ListingPublicSerializer
from .services import get_public_listing


PublicListingSearchResponseSerializer = inline_serializer(
    name="PublicListingSearchResponse",
    fields={
        "count": serializers.IntegerField(),
        "next": serializers.IntegerField(allow_null=True),
        "previous": serializers.IntegerField(allow_null=True),
        "results": ListingPublicSerializer(many=True),
    },
)


def _record_analytics_safely(recorder, **kwargs):
    try:
        recorder(**kwargs)
    except Exception:
        public_analytics.logger.exception("Public analytics recording failed.")


class PublicListingCollectionView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = ListingPublicSerializer

    @extend_schema(
        operation_id="public_listing_list",
        parameters=[PublicListingSearchParamsSerializer],
        responses={200: PublicListingSearchResponseSerializer},
    )
    def get(self, request, *args, **kwargs):
        queryset = get_public_listing_search_queryset(request.query_params)
        page = paginate_public_listings(queryset, request.query_params)
        _record_analytics_safely(
            public_analytics.record_public_listing_search,
            params=request.query_params,
            result_count=page.count,
        )
        payload = page.as_dict()
        payload["results"] = self.get_serializer(page.results, many=True).data
        return Response(payload)


class PublicListingDetailView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = ListingPublicSerializer

    @extend_schema(operation_id="public_listing_retrieve", responses={200: ListingPublicSerializer})
    def get(self, request, listing_id, *args, **kwargs):
        listing = get_public_listing(listing_id=listing_id)
        _record_analytics_safely(public_analytics.record_public_listing_view, listing=listing)
        return Response(self.get_serializer(listing).data)
