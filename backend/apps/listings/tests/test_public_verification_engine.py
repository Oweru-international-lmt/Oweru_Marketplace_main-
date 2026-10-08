from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.listings.public_search import get_public_listing_search_queryset
from apps.listings.serializers import ListingPublicSerializer
from apps.properties.services import update_property_record
from apps.roles.catalog import ROLE_OWNER
from apps.verification.models import PropertyVerification

from .test_public_verification import create_user, grant_role, identity_for, listing


pytestmark = pytest.mark.django_db


def approved_verification(property_record, *, kind, expires_at=None):
    now = timezone.now()
    return PropertyVerification.objects.create(
        property=property_record,
        kind=kind,
        status=PropertyVerification.Status.APPROVED,
        submitted_by=property_record.created_by,
        submitted_at=now,
        reviewed_by=create_user(),
        reviewed_at=now,
        expires_at=expires_at or now + timedelta(days=30),
    )


def public_summary(target):
    return ListingPublicSerializer(target).data["lister"]["verification"]


def verified_listing(level, *, status=None):
    user = create_user()
    grant_role(user, ROLE_OWNER)
    target = listing(user, status=status or "ACTIVE")
    if level:
        identity_for(user)
    if level >= 2:
        approved_verification(target.property, kind=PropertyVerification.Kind.DOCUMENT)
    if level >= 3:
        approved_verification(target.property, kind=PropertyVerification.Kind.FIELD)
    return target


def result_ids(minimum_level):
    return set(
        get_public_listing_search_queryset({"min_verification_level": str(minimum_level)})
        .values_list("listing_id", flat=True)
    )


def test_public_summary_uses_the_canonical_level_zero_to_three_ladder():
    level_zero = verified_listing(0)
    level_one = verified_listing(1)
    level_two = verified_listing(2)
    level_three = verified_listing(3)

    assert public_summary(level_zero) == {"level": 0, "label": "Not verified", "is_verified": False}
    assert public_summary(level_one) == {"level": 1, "label": "Identity verified", "is_verified": True}
    assert public_summary(level_two) == {"level": 2, "label": "Property verified", "is_verified": True}
    # Historic FIELD approval is evidence, not a completed Full Check.
    assert public_summary(level_three) == {"level": 2, "label": "Property verified", "is_verified": True}


def test_public_summary_cascades_when_persisted_prerequisites_stop_being_effective():
    target = verified_listing(3)
    identity = target.lister.lister_identity
    document = target.property.verifications.get(kind=PropertyVerification.Kind.DOCUMENT)
    field = target.property.verifications.get(kind=PropertyVerification.Kind.FIELD)

    field.status = PropertyVerification.Status.REVOKED
    field.revoked_at = timezone.now()
    field.save(update_fields=["status", "revoked_at", "updated_at"])
    assert public_summary(target)["level"] == 2

    document.status = PropertyVerification.Status.EXPIRED
    document.save(update_fields=["status", "updated_at"])
    assert public_summary(target)["level"] == 1

    identity.expires_at = timezone.now() - timedelta(seconds=1)
    identity.save(update_fields=["expires_at", "updated_at"])
    assert public_summary(target)["level"] == 0


def test_material_property_change_immediately_removes_public_document_and_field_levels():
    target = verified_listing(3)

    update_property_record(
        actor=target.lister,
        property_record=target.property,
        stated_size=target.property.stated_size + 1,
    )

    assert public_summary(target)["level"] == 1
    assert set(target.property.verifications.values_list("status", flat=True)) == {PropertyVerification.Status.REVOKED}


def test_public_search_minimum_level_uses_the_same_ladder_and_keeps_hidden_listings_hidden():
    level_zero = verified_listing(0)
    level_one = verified_listing(1)
    level_two = verified_listing(2)
    level_three = verified_listing(3)
    hidden_level_three = verified_listing(3, status="SOLD")

    assert {level_zero.listing_id, level_one.listing_id, level_two.listing_id, level_three.listing_id}.issubset(result_ids(0))
    assert level_zero.listing_id not in result_ids(1)
    assert {level_one.listing_id, level_two.listing_id, level_three.listing_id}.issubset(result_ids(1))
    assert {level_two.listing_id, level_three.listing_id}.issubset(result_ids(2))
    assert level_one.listing_id not in result_ids(2)
    assert level_three.listing_id not in result_ids(3)
    assert level_two.listing_id not in result_ids(3)
    assert hidden_level_three.listing_id not in result_ids(0)
    assert hidden_level_three.listing_id not in result_ids(3)


def test_public_level_serialization_uses_annotated_data_without_per_listing_verification_queries():
    for level in range(4):
        verified_listing(level)

    with CaptureQueriesContext(connection) as captured:
        payload = ListingPublicSerializer(list(get_public_listing_search_queryset()), many=True).data

    assert {item["lister"]["verification"]["level"] for item in payload} == {0, 1, 2}
    assert len(captured) <= 3
    rendered = repr(payload).lower()
    for forbidden in ("evidence_ref", "reviewed_by", "rejection_reason", "expires_at", "subject_snapshot"):
        assert forbidden not in rendered
