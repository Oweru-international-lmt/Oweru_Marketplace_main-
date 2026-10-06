from decimal import Decimal
from io import BytesIO
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.utils import timezone
from PIL import Image
from rest_framework.settings import api_settings
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.lister_identity.models import ListerIdentity
from apps.listings import public_analytics
from apps.listings.models import Listing, ListingPhoto
from apps.listings.public_views import PublicListingCollectionView, PublicListingDetailView
from apps.localities.models import District, Locality, Region, Ward
from apps.media.models import MediaVariant
from apps.media.services import create_image_media
from apps.media.storage import get_private_media_storage, reset_in_memory_storage
from apps.properties.duplicate_services import record_possible_duplicate
from apps.properties.models import PossibleDuplicate, PropertyRecord
from apps.roles.catalog import ROLE_OWNER
from apps.roles.models import Role, UserRole
from apps.roles.services import bootstrap_canonical_roles


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def media_settings():
    reset_in_memory_storage()
    with override_settings(
        MEDIA_STORAGE_BACKEND="memory",
        MEDIA_MAX_UPLOAD_BYTES=1024 * 1024,
        MEDIA_ALLOWED_IMAGE_MIME_TYPES=["image/jpeg", "image/png", "image/webp"],
        MEDIA_MAX_IMAGE_WIDTH=80,
        MEDIA_MAX_IMAGE_HEIGHT=60,
        MEDIA_SIGNED_URL_TTL_SECONDS=123,
    ):
        yield
    reset_in_memory_storage()


def create_user(email=None):
    email = email or f"public-hardening-{uuid.uuid4().hex[:10]}@example.test"
    return get_user_model().objects.create_user(
        email=email,
        phone=f"+2557{abs(hash(email)) % 100000000:08d}",
        full_name="Public Hardening User",
        password="StrongPass123!",
    )


def grant_role(user, role_code=ROLE_OWNER):
    bootstrap_canonical_roles()
    return UserRole.objects.create(user=user, role=Role.objects.get(code=role_code))


def hierarchy(prefix=None):
    prefix = prefix or f"PublicHardening{uuid.uuid4().hex[:8]}"
    region = Region.objects.create(name=f"{prefix} Region")
    district = District.objects.create(region=region, name=f"{prefix} District")
    ward = Ward.objects.create(district=district, name=f"{prefix} Ward")
    locality = Locality.objects.create(ward=ward, name=f"{prefix} Street", kind=Locality.Kind.STREET, approved=True)
    return region, district, ward, locality


def property_record(owner):
    region, district, ward, locality = hierarchy()
    return PropertyRecord.objects.create(
        property_id=f"OWR-{uuid.uuid4().hex[:16].upper()}",
        category=PropertyRecord.Category.LAND,
        pin=Point(39.2083, -6.7924, srid=4326),
        boundary=None,
        region=region,
        district=district,
        ward=ward,
        locality=locality,
        stated_size=Decimal("1200.00"),
        size_unit="sqm",
        title_type=PropertyRecord.TitleType.UNKNOWN,
        created_by=owner,
    )


def listing(owner=None, *, status=Listing.Status.ACTIVE, selling_price=Decimal("100000000")):
    owner = owner or create_user()
    return Listing.objects.create(
        listing_id=f"LST-{uuid.uuid4().hex[:16].upper()}",
        property=property_record(owner),
        lister=owner,
        lister_kind=Listing.ListerKind.OWNER,
        selling_price=selling_price,
        owner_price=selling_price,
        currency=Listing.Currency.TZS,
        status=status,
        description="Public hardening listing.",
        features=[],
    )


def verified_identity(user):
    return ListerIdentity.objects.create(
        user=user,
        national_id_number=f"NIDA-{uuid.uuid4().hex[:12]}",
        national_id_photo_ref="private/id-photo.jpg",
        live_selfie_ref="private/selfie.jpg",
        status=ListerIdentity.Status.APPROVED,
        reviewed_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(days=30),
    )


def image_upload(color=(130, 100, 90)):
    output = BytesIO()
    Image.new("RGB", (32, 24), color=color).save(output, format="JPEG")
    return SimpleUploadedFile(f"hardening-{uuid.uuid4().hex}.jpg", output.getvalue(), content_type="image/jpeg")


def listing_media(actor, target_listing, *, color=(130, 100, 90)):
    return create_image_media(actor=actor, owner_type="listing", owner_id=target_listing.listing_id, image=image_upload(color=color))


def add_photo(actor, target_listing, *, position=0, color=(130, 100, 90)):
    media = listing_media(actor, target_listing, color=color)
    return ListingPhoto.objects.create(listing=target_listing, media=media, position=position)


def response_text(response):
    return repr(response.data).lower()


def test_public_search_analytics_records_safe_allowlisted_metadata(monkeypatch):
    target = listing()
    events = []
    monkeypatch.setattr(public_analytics.logger, "info", lambda message: events.append(message))

    response = APIClient().get(
        "/api/v1/public/listings/",
        {
            "category": PropertyRecord.Category.LAND,
            "min_price": "1",
            "sort": "PRICE_ASC",
            "page": "1",
            "page_size": "20",
        },
    )
    payload = public_analytics.record_public_listing_search(
        params={"category": PropertyRecord.Category.LAND, "min_price": "1", "sort": "PRICE_ASC", "page": "1", "page_size": "20"},
        result_count=1,
    )

    assert response.status_code == 200
    assert target.listing_id in {item["listing_id"] for item in response.data["results"]}
    assert payload["event"] == public_analytics.PUBLIC_LISTING_SEARCH
    assert payload["metadata"] == {
        "filter_names": ["category", "min_price"],
        "sort": "PRICE_ASC",
        "result_count": 1,
        "page": 1,
        "page_size": 20,
    }
    rendered = repr(payload).lower()
    for forbidden in ["owner_price", "pin", "coordinates", "authorization", "cookie", "phone", "file_key", "file_hash"]:
        assert forbidden not in rendered
    assert AuditLog.objects.filter(action=public_analytics.PUBLIC_LISTING_SEARCH).count() == 0


def test_public_view_analytics_failure_does_not_break_success(monkeypatch):
    target = listing()

    def fail(*args, **kwargs):
        raise RuntimeError("analytics backend down")

    monkeypatch.setattr(public_analytics, "record_public_listing_search", fail)
    monkeypatch.setattr(public_analytics, "record_public_listing_view", fail)

    search = APIClient().get("/api/v1/public/listings/")
    detail = APIClient().get(f"/api/v1/public/listings/{target.listing_id}/")

    assert search.status_code == 200
    assert detail.status_code == 200


def test_rejected_hostile_query_parameters_do_not_record_analytics(monkeypatch):
    events = []
    monkeypatch.setattr(public_analytics, "record_public_listing_search", lambda **kwargs: events.append(kwargs))

    response = APIClient().get("/api/v1/public/listings/", {"raw_sql": "1=1", "owner_price": "1"})

    assert response.status_code == 400
    assert events == []


def test_visible_detail_records_view_but_hidden_and_missing_do_not(monkeypatch):
    visible = listing(status=Listing.Status.ACTIVE)
    hidden = listing(status=Listing.Status.SUSPENDED)
    events = []
    monkeypatch.setattr(public_analytics, "record_public_listing_view", lambda **kwargs: events.append(kwargs["listing"].listing_id))
    client = APIClient()

    visible_response = client.get(f"/api/v1/public/listings/{visible.listing_id}/")
    hidden_response = client.get(f"/api/v1/public/listings/{hidden.listing_id}/")
    missing_response = client.get("/api/v1/public/listings/LST-MISSING/")

    assert visible_response.status_code == 200
    assert hidden_response.status_code == 404
    assert missing_response.status_code == 404
    assert hidden_response.data == missing_response.data
    assert events == [visible.listing_id]


def test_public_media_signing_display_only_no_original_fallback_and_no_signed_url_analytics(monkeypatch):
    owner = create_user()
    grant_role(owner)
    target = listing(owner)
    photo = add_photo(owner, target)
    photo.media.variants.filter(kind=MediaVariant.Kind.ORIGINAL).update(file_key="private/original-secret.jpg")
    analytics = []
    monkeypatch.setattr(public_analytics, "record_public_listing_view", lambda **kwargs: analytics.append({"listing_id": kwargs["listing"].listing_id}))

    response = APIClient().get(f"/api/v1/public/listings/{target.listing_id}/")
    signed = get_private_media_storage().signed_requests[-1]
    display_key = photo.media.variants.get(kind=MediaVariant.Kind.DISPLAY).file_key

    assert response.status_code == 200
    assert signed["key"] == display_key
    assert signed["expires_in"] == 123
    rendered = response_text(response)
    assert "original" not in rendered
    assert "file_key" not in rendered
    assert "file_hash" not in rendered
    assert "signed-media" not in repr(analytics).lower()


def test_pagination_hardening_and_deterministic_ordering():
    with override_settings(PUBLIC_LISTING_PAGE_SIZE=2, PUBLIC_LISTING_MAX_PAGE_SIZE=3):
        first = listing(selling_price=Decimal("100"))
        second = listing(selling_price=Decimal("200"))
        third = listing(selling_price=Decimal("300"))
        client = APIClient()

        default_page = client.get("/api/v1/public/listings/")
        max_page = client.get("/api/v1/public/listings/", {"page_size": 3})
        excessive = client.get("/api/v1/public/listings/", {"page_size": 4})
        malformed = client.get("/api/v1/public/listings/", {"page_size": "all"})
        ordered = client.get("/api/v1/public/listings/", {"sort": "PRICE_ASC", "page_size": 3})

    assert len(default_page.data["results"]) == 2
    assert len(max_page.data["results"]) == 3
    assert excessive.status_code == 400
    assert malformed.status_code == 400
    assert [item["listing_id"] for item in ordered.data["results"]] == [first.listing_id, second.listing_id, third.listing_id]


def test_public_search_detail_query_counts_do_not_grow_per_listing_or_photo():
    owner = create_user()
    grant_role(owner)
    verified_identity(owner)
    listings = [listing(owner) for _ in range(3)]
    for index, item in enumerate(listings):
        add_photo(owner, item, position=0, color=(90 + index, 100, 100))
        add_photo(owner, item, position=1, color=(100, 90 + index, 100))

    with CaptureQueriesContext(connection) as search_queries:
        response = APIClient().get("/api/v1/public/listings/", {"page_size": 3})
        assert response.status_code == 200
        assert len(response.data["results"]) == 3

    with CaptureQueriesContext(connection) as detail_queries:
        detail = APIClient().get(f"/api/v1/public/listings/{listings[0].listing_id}/")
        assert detail.status_code == 200
        assert len(detail.data["photos"]) == 2

    assert len(search_queries) <= 5
    assert len(detail_queries) <= 4


def test_public_response_privacy_verification_and_duplicate_isolation():
    owner = create_user()
    grant_role(owner)
    owner.is_verified = True
    owner.verification_level = 3
    first = listing(owner)
    second = listing()
    record_possible_duplicate(property_a=first.property, property_b=second.property, signals=[PossibleDuplicate.SIGNAL_PIN_PROXIMITY])

    response = APIClient().get(f"/api/v1/public/listings/{first.listing_id}/")
    rendered = response_text(response)

    assert response.status_code == 200
    assert response.data["lister"]["verification"] == {"level": 0, "label": "Not verified", "is_verified": False}
    for forbidden in [
        "owner_price",
        "pin",
        "boundary",
        "coordinates",
        "created_by",
        "email",
        "phone",
        "national_id",
        "file_key",
        "file_hash",
        "possibleduplicate",
        "pin_proximity",
        "roles",
        "permissions",
        "audit",
    ]:
        assert forbidden not in rendered


def test_private_endpoints_remain_private_and_public_views_keep_global_throttles():
    owner = create_user()
    grant_role(owner)
    target = listing(owner)
    photo = add_photo(owner, target)
    client = APIClient()

    assert client.get("/api/v1/listings/").status_code == 401
    assert client.get(f"/api/v1/listings/{target.listing_id}/").status_code == 401
    assert client.get("/api/v1/properties/").status_code == 401
    assert client.get(f"/api/v1/media/{photo.media.media_id}/access/").status_code == 401
    assert client.get("/api/v1/management/property-duplicates/").status_code == 401
    assert client.get("/api/v1/lister-identity/me/").status_code == 401
    assert PublicListingCollectionView.throttle_classes == api_settings.DEFAULT_THROTTLE_CLASSES
    assert PublicListingDetailView.throttle_classes == api_settings.DEFAULT_THROTTLE_CLASSES
