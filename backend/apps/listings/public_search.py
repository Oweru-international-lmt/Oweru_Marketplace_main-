from dataclasses import dataclass
from decimal import Decimal
from math import ceil

from django.conf import settings
from rest_framework import serializers
from rest_framework.exceptions import NotFound

from apps.properties.models import PropertyRecord
from apps.verification.services import filter_listing_queryset_by_minimum_effective_verification_level

from . import services


SORT_NEWEST = "NEWEST"
SORT_PRICE_ASC = "PRICE_ASC"
SORT_PRICE_DESC = "PRICE_DESC"
PUBLIC_LISTING_SORT_CHOICES = (SORT_NEWEST, SORT_PRICE_ASC, SORT_PRICE_DESC)


class RejectUnknownSearchFieldsMixin:
    def to_internal_value(self, data):
        data = data or {}
        if not isinstance(data, dict):
            raise serializers.ValidationError("Expected an object.")
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({field: "This filter is not supported." for field in sorted(unknown)})
        return super().to_internal_value(data)


class PublicListingSearchParamsSerializer(RejectUnknownSearchFieldsMixin, serializers.Serializer):
    category = serializers.ChoiceField(choices=PropertyRecord.Category.choices, required=False)
    region = serializers.UUIDField(required=False)
    district = serializers.UUIDField(required=False)
    ward = serializers.UUIDField(required=False)
    min_price = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0"), required=False)
    max_price = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0"), required=False)
    min_size = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0"), required=False)
    max_size = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0"), required=False)
    title_type = serializers.ChoiceField(choices=PropertyRecord.TitleType.choices, required=False)
    min_verification_level = serializers.IntegerField(
        min_value=0,
        max_value=3,
        required=False,
        help_text="Minimum derived verification level: 0, 1, 2, or 3.",
    )
    sort = serializers.ChoiceField(choices=PUBLIC_LISTING_SORT_CHOICES, default=SORT_NEWEST, required=False)
    page = serializers.IntegerField(min_value=1, required=False)
    page_size = serializers.IntegerField(min_value=1, required=False)

    def validate(self, attrs):
        if "min_price" in attrs and "max_price" in attrs and attrs["min_price"] > attrs["max_price"]:
            raise serializers.ValidationError({"max_price": "Must be greater than or equal to min_price."})
        if "min_size" in attrs and "max_size" in attrs and attrs["min_size"] > attrs["max_size"]:
            raise serializers.ValidationError({"max_size": "Must be greater than or equal to min_size."})
        if attrs.get("page_size", settings.PUBLIC_LISTING_PAGE_SIZE) > settings.PUBLIC_LISTING_MAX_PAGE_SIZE:
            raise serializers.ValidationError({
                "page_size": f"Must be less than or equal to {settings.PUBLIC_LISTING_MAX_PAGE_SIZE}."
            })
        return attrs


def validate_public_listing_search_params(params=None):
    serializer = PublicListingSearchParamsSerializer(data=params or {})
    serializer.is_valid(raise_exception=True)
    return dict(serializer.validated_data)


def apply_public_listing_filters(queryset, params):
    filters = {}
    if "category" in params:
        filters["property__category"] = params["category"]
    if "region" in params:
        filters["property__region_id"] = params["region"]
    if "district" in params:
        filters["property__district_id"] = params["district"]
    if "ward" in params:
        filters["property__ward_id"] = params["ward"]
    if "min_price" in params:
        filters["selling_price__gte"] = params["min_price"]
    if "max_price" in params:
        filters["selling_price__lte"] = params["max_price"]
    if "min_size" in params:
        filters["property__stated_size__gte"] = params["min_size"]
    if "max_size" in params:
        filters["property__stated_size__lte"] = params["max_size"]
    if "title_type" in params:
        filters["property__title_type"] = params["title_type"]
    queryset = queryset.filter(**filters)
    if "min_verification_level" in params:
        return filter_listing_queryset_by_minimum_effective_verification_level(
            queryset,
            minimum_level=params["min_verification_level"],
        )
    return queryset


def apply_public_listing_sorting(queryset, sort):
    if sort == SORT_PRICE_ASC:
        return queryset.order_by("selling_price", "-created_at", "-id")
    if sort == SORT_PRICE_DESC:
        return queryset.order_by("-selling_price", "-created_at", "-id")
    if sort == SORT_NEWEST:
        return queryset.order_by("-created_at", "-id")
    raise serializers.ValidationError({"sort": "Unsupported sort option."})


def get_public_listing_search_queryset(params=None):
    validated = validate_public_listing_search_params(params)
    queryset = services.get_public_listings()
    queryset = apply_public_listing_filters(queryset, validated)
    return apply_public_listing_sorting(queryset, validated.get("sort", SORT_NEWEST))


@dataclass(frozen=True)
class PublicListingPage:
    count: int
    next: int | None
    previous: int | None
    results: list

    def as_dict(self):
        return {
            "count": self.count,
            "next": self.next,
            "previous": self.previous,
            "results": self.results,
        }


def paginate_public_listings(queryset, params=None):
    validated = validate_public_listing_search_params(params)
    page = validated.get("page", 1)
    page_size = validated.get("page_size", settings.PUBLIC_LISTING_PAGE_SIZE)
    count = queryset.count()
    max_page = max(1, ceil(count / page_size))
    if page > max_page:
        raise NotFound("Invalid page.")

    start = (page - 1) * page_size
    end = start + page_size
    results = list(queryset[start:end])
    return PublicListingPage(
        count=count,
        next=page + 1 if end < count else None,
        previous=page - 1 if page > 1 else None,
        results=results,
    )
