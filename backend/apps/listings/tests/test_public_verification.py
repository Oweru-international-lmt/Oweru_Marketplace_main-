from decimal import Decimal
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

from apps.lister_identity.models import ListerIdentity
from apps.lister_identity.services import get_public_verification_summary
from apps.listings.models import Listing
from apps.listings.public_search import get_public_listing_search_queryset
from apps.listings.serializers import ListingPublicSerializer
from apps.localities.models import District, Locality, Region, Ward
from apps.properties.models import PropertyRecord
from apps.roles.catalog import ROLE_AGENT, ROLE_MANAGEMENT, ROLE_OWNER
from apps.roles.models import Role, UserRole
from apps.roles.services import bootstrap_canonical_roles


pytestmark = pytest.mark.django_db


def create_user(email=None):
    email = email or f"public-verification-{uuid.uuid4().hex[:10]}@example.test"
    return get_user_model().objects.create_user(
        email=email,
        phone=f"+2557{abs(hash(email)) % 100000000:08d}",
        full_name="Public Verification User",
        password="StrongPass123!",
    )


def grant_role(user, role_code):
    bootstrap_canonical_roles()
    return UserRole.objects.create(user=user, role=Role.objects.get(code=role_code))


def hierarchy(prefix=None):
    prefix = prefix or f"PublicVerification{uuid.uuid4().hex[:8]}"
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


def listing(owner, *, lister_kind=Listing.ListerKind.OWNER, status=Listing.Status.ACTIVE):
    selling_price = Decimal("100000000")
    owner_price = selling_price if lister_kind == Listing.ListerKind.OWNER else Decimal("90000000")
    return Listing.objects.create(
        listing_id=f"LST-{uuid.uuid4().hex[:16].upper()}",
        property=property_record(owner),
        lister=owner,
        lister_kind=lister_kind,
        selling_price=selling_price,
        owner_price=owner_price,
        currency=Listing.Currency.TZS,
        status=status,
        description="Public verification listing.",
        features=[],
    )


def identity_for(user, *, status=ListerIdentity.Status.APPROVED, expires_at=None):
    if expires_at is None and status == ListerIdentity.Status.APPROVED:
        expires_at = timezone.now() + timezone.timedelta(days=30)
    return ListerIdentity.objects.create(
        user=user,
        national_id_number=f"NIDA-{uuid.uuid4().hex[:12]}",
        national_id_photo_ref="private/id-photo.jpg",
        live_selfie_ref="private/selfie.jpg",
        status=status,
        submitted_at=timezone.now(),
        reviewed_at=timezone.now() if status != ListerIdentity.Status.PENDING else None,
        expires_at=expires_at,
        review_reason="private reason" if status == ListerIdentity.Status.REJECTED else "",
    )


def verification_from_listing(target):
    return ListingPublicSerializer(target).data["lister"]["verification"]


def test_level_0_for_missing_pending_rejected_and_expired_identity():
    missing_user = create_user("missing-identity@example.test")
    pending_user = create_user("pending-identity@example.test")
    rejected_user = create_user("rejected-identity@example.test")
    expired_user = create_user("expired-identity@example.test")
    for user in (missing_user, pending_user, rejected_user, expired_user):
        grant_role(user, ROLE_OWNER)
    identity_for(pending_user, status=ListerIdentity.Status.PENDING, expires_at=None)
    identity_for(rejected_user, status=ListerIdentity.Status.REJECTED, expires_at=None)
    identity_for(expired_user, status=ListerIdentity.Status.APPROVED, expires_at=timezone.now() - timezone.timedelta(days=1))

    for user in (missing_user, pending_user, rejected_user, expired_user):
        summary = get_public_verification_summary(user=user)
        listing_summary = verification_from_listing(listing(user))
        assert summary == {"level": 0, "label": "Not verified", "is_verified": False}
        assert listing_summary == summary


def test_level_1_for_canonically_approved_identity():
    user = create_user()
    grant_role(user, ROLE_OWNER)
    identity_for(user)

    summary = get_public_verification_summary(user=user)

    assert summary == {"level": 1, "label": "Identity verified", "is_verified": True}
    assert verification_from_listing(listing(user)) == summary


def test_fake_claims_cannot_produce_level_1():
    user = create_user()
    grant_role(user, ROLE_OWNER)
    user.is_verified = True
    user.verification_level = 3
    user.identity_verified = True
    user.role = ROLE_OWNER
    user.roles = [ROLE_OWNER]

    assert get_public_verification_summary(user=user) == {"level": 0, "label": "Not verified", "is_verified": False}
    assert verification_from_listing(listing(user)) == {"level": 0, "label": "Not verified", "is_verified": False}


def test_owner_agent_lister_kind_comes_from_listing_not_management_assignment():
    owner = create_user("public-owner-kind@example.test")
    agent = create_user("public-agent-kind@example.test")
    grant_role(owner, ROLE_OWNER)
    grant_role(agent, ROLE_AGENT)
    grant_role(owner, ROLE_MANAGEMENT)
    grant_role(agent, ROLE_MANAGEMENT)
    identity_for(owner)
    identity_for(agent)

    owner_data = ListingPublicSerializer(listing(owner, lister_kind=Listing.ListerKind.OWNER)).data["lister"]
    agent_data = ListingPublicSerializer(listing(agent, lister_kind=Listing.ListerKind.AGENT)).data["lister"]

    assert owner_data["lister_kind"] == Listing.ListerKind.OWNER
    assert agent_data["lister_kind"] == Listing.ListerKind.AGENT
    assert "MANAGEMENT" not in repr(owner_data)
    assert "MANAGEMENT" not in repr(agent_data)


def test_public_lister_response_privacy():
    user = create_user()
    grant_role(user, ROLE_OWNER)
    identity_for(user, status=ListerIdentity.Status.REJECTED, expires_at=None)

    data = ListingPublicSerializer(listing(user)).data["lister"]
    rendered = repr(data).lower()

    assert set(data) == {"display_name", "lister_kind", "verification", "member_since"}
    for forbidden in [
        "email",
        "phone",
        "national_id_number",
        "national_id_photo_ref",
        "live_selfie_ref",
        "private/id-photo",
        "private/selfie",
        "reviewed_by",
        "review_reason",
        "private reason",
        "roles",
        "permissions",
        "submitted_at",
        "reviewed_at",
        "expires_at",
    ]:
        assert forbidden not in rendered


def test_min_verification_level_filter():
    unverified_user = create_user("unverified-filter@example.test")
    verified_user = create_user("verified-filter@example.test")
    grant_role(unverified_user, ROLE_OWNER)
    grant_role(verified_user, ROLE_OWNER)
    unverified = listing(unverified_user)
    verified = listing(verified_user)
    identity_for(verified_user)

    level_zero = set(get_public_listing_search_queryset({"min_verification_level": "0"}).values_list("listing_id", flat=True))
    level_one = set(get_public_listing_search_queryset({"min_verification_level": "1"}).values_list("listing_id", flat=True))

    assert {unverified.listing_id, verified.listing_id}.issubset(level_zero)
    assert verified.listing_id in level_one
    assert unverified.listing_id not in level_one


@pytest.mark.parametrize("value", ["2", "3", "-1", "abc"])
def test_unsupported_min_verification_level_rejected(value):
    response = APIClient().get("/api/v1/public/listings/", {"min_verification_level": value})

    assert response.status_code == 400


def test_search_and_detail_return_same_verification_structure_and_profile_is_consistent():
    user = create_user()
    grant_role(user, ROLE_OWNER)
    identity = identity_for(user)
    target = listing(user)
    client = APIClient()

    search = client.get("/api/v1/public/listings/", {"min_verification_level": "1"})
    detail = client.get(f"/api/v1/public/listings/{target.listing_id}/")
    profile = client.get(f"/api/v1/listers/{identity.pk}/")

    search_item = next(item for item in search.data["results"] if item["listing_id"] == target.listing_id)
    assert search_item["lister"]["verification"] == detail.data["lister"]["verification"]
    assert profile.status_code == 200
    assert profile.data["is_verified"] == detail.data["lister"]["verification"]["is_verified"]


def test_public_verification_serialization_avoids_identity_n_plus_one_queries():
    verified_user = create_user("verified-query@example.test")
    unverified_user = create_user("unverified-query@example.test")
    grant_role(verified_user, ROLE_OWNER)
    grant_role(unverified_user, ROLE_OWNER)
    identity_for(verified_user)
    listing(verified_user)
    listing(unverified_user)

    with CaptureQueriesContext(connection) as captured:
        data = ListingPublicSerializer(list(get_public_listing_search_queryset()), many=True).data
        assert len(data) >= 2
        for item in data:
            assert "verification" in item["lister"]

    assert len(captured) == 3
