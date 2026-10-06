import json
import logging

from .public_search import SORT_NEWEST


PUBLIC_LISTING_SEARCH = "public_listing.search"
PUBLIC_LISTING_VIEW = "public_listing.view"

SEARCH_FILTER_FIELDS = frozenset({
    "category",
    "region",
    "district",
    "ward",
    "min_price",
    "max_price",
    "min_size",
    "max_size",
    "title_type",
    "min_verification_level",
})

logger = logging.getLogger("apps.listings.public_analytics")


def _safe_search_metadata(*, params, result_count):
    filter_names = sorted(field for field in SEARCH_FILTER_FIELDS if field in params)
    return {
        "filter_names": filter_names,
        "sort": params.get("sort", SORT_NEWEST),
        "result_count": int(result_count),
        "page": int(params.get("page", 1)),
        "page_size": int(params.get("page_size")) if "page_size" in params else None,
    }


def record_public_listing_search(*, params, result_count):
    payload = {
        "event": PUBLIC_LISTING_SEARCH,
        "metadata": _safe_search_metadata(params=params, result_count=result_count),
    }
    logger.info(json.dumps(payload, sort_keys=True))
    return payload


def record_public_listing_view(*, listing):
    payload = {
        "event": PUBLIC_LISTING_VIEW,
        "metadata": {
            "listing_id": listing.listing_id,
        },
    }
    logger.info(json.dumps(payload, sort_keys=True))
    return payload
