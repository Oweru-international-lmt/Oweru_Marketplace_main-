from datetime import timedelta
from decimal import Decimal
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.exceptions import FieldDoesNotExist
from django.utils import timezone
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.lister_identity.models import ListerIdentity
from apps.localities.models import District, Locality, Region, Ward
from apps.properties.models import PropertyRecord
from apps.verification.models import PropertyVerification, PropertyVerificationEvidence
from apps.verification.services import (
    filter_queryset_with_effective_property_verification,
    get_effective_verification_level,
)


pytestmark = pytest.mark.django_db


def create_user():
    token = uuid.uuid4().hex[:12]
    return get_user_model().objects.create_user(
        email=f"verification-{token}@example.test",
        phone=f"+2557{int(token[:8], 16) % 100000000:08d}",
        full_name="Verification Test User",
        password="StrongPass123!",
    )


def create_property(owner):
    token = uuid.uuid4().hex[:10]
    region = Region.objects.create(name=f"Verification {token} Region")
    district = District.objects.create(region=region, name=f"Verification {token} District")
    ward = Ward.objects.create(district=district, name=f"Verification {token} Ward")
    locality = Locality.objects.create(
        ward=ward,
        name=f"Verification {token} Street",
        kind=Locality.Kind.STREET,
        approved=True,
    )
    return PropertyRecord.objects.create(
        property_id=f"OWR-{uuid.uuid4().hex[:16].upper()}",
        category=PropertyRecord.Category.LAND,
        pin=Point(39.2083, -6.7924, srid=4326),
        region=region,
        district=district,
        ward=ward,
        locality=locality,
        stated_size=Decimal("1200.00"),
        size_unit="sqm",
        title_type=PropertyRecord.TitleType.UNKNOWN,
        created_by=owner,
    )


def create_identity(user, *, status=ListerIdentity.Status.APPROVED, expires_at=None):
    return ListerIdentity.objects.create(
        user=user,
        national_id_number="NIDA-TEST",
        national_id_photo_ref="private/id-reference",
        live_selfie_ref="private/selfie-reference",
        status=status,
        expires_at=expires_at,
    )


def create_verification(
    property_record,
    *,
    kind,
    status=PropertyVerification.Status.APPROVED,
    expires_at=None,
    reviewer=None,
):
    submitter = property_record.created_by
    reviewer = reviewer or create_user()
    now = timezone.now()
    values = {
        "property": property_record,
        "kind": kind,
        "status": status,
        "submitted_by": submitter,
        "submitted_at": now,
    }
    if status == PropertyVerification.Status.APPROVED:
        values.update(reviewed_by=reviewer, reviewed_at=now, expires_at=expires_at or now + timedelta(days=30))
    elif status == PropertyVerification.Status.REJECTED:
        values.update(reviewed_by=reviewer, reviewed_at=now, rejection_reason="Evidence does not match.")
    elif status == PropertyVerification.Status.REVOKED:
        values.update(revoked_at=now)
    else:
        values["expires_at"] = expires_at
    return PropertyVerification.objects.create(**values)


@pytest.mark.parametrize(
    ("status", "expires_at", "expected"),
    [
        (ListerIdentity.Status.PENDING, None, 0),
        (ListerIdentity.Status.REJECTED, None, 0),
        (ListerIdentity.Status.EXPIRED, timezone.now() - timedelta(seconds=1), 0),
        (ListerIdentity.Status.APPROVED, timezone.now() + timedelta(days=1), 1),
    ],
)
def test_level_one_uses_only_approved_unexpired_persisted_identity(status, expires_at, expected):
    user = create_user()
    create_identity(user, status=status, expires_at=expires_at)

    assert get_effective_verification_level(user=user) == expected


def test_no_identity_is_level_zero_and_fake_attributes_do_not_raise_level():
    user = create_user()
    user.verification_level = 3
    user.is_verified = True

    assert get_effective_verification_level(user=user) == 0


def test_document_requires_level_one_and_valid_document_yields_level_two():
    user = create_user()
    property_record = create_property(user)
    create_verification(property_record, kind=PropertyVerification.Kind.DOCUMENT)

    assert get_effective_verification_level(user=user, property_record=property_record) == 0

    create_identity(user, expires_at=timezone.now() + timedelta(days=1))

    assert get_effective_verification_level(user=user, property_record=property_record) == 2


@pytest.mark.parametrize(
    "status",
    [
        PropertyVerification.Status.PENDING,
        PropertyVerification.Status.REJECTED,
        PropertyVerification.Status.EXPIRED,
        PropertyVerification.Status.REVOKED,
    ],
)
def test_invalid_document_statuses_fall_back_to_level_one(status):
    user = create_user()
    property_record = create_property(user)
    create_identity(user, expires_at=timezone.now() + timedelta(days=1))
    create_verification(property_record, kind=PropertyVerification.Kind.DOCUMENT, status=status)

    assert get_effective_verification_level(user=user, property_record=property_record) == 1


def test_field_requires_effective_document_and_invalid_field_falls_back_to_level_two():
    user = create_user()
    property_record = create_property(user)
    create_identity(user, expires_at=timezone.now() + timedelta(days=1))
    create_verification(property_record, kind=PropertyVerification.Kind.FIELD)

    assert get_effective_verification_level(user=user, property_record=property_record) == 1

    create_verification(property_record, kind=PropertyVerification.Kind.DOCUMENT)

    assert get_effective_verification_level(user=user, property_record=property_record) == 2

    property_record.verifications.filter(kind=PropertyVerification.Kind.FIELD).update(
        status=PropertyVerification.Status.REVOKED,
        revoked_at=timezone.now(),
    )

    assert get_effective_verification_level(user=user, property_record=property_record) == 2


def test_expiry_collapses_the_ladder_to_the_last_effective_level():
    user = create_user()
    property_record = create_property(user)
    now = timezone.now()
    identity = create_identity(user, expires_at=now + timedelta(days=1))
    document = create_verification(
        property_record,
        kind=PropertyVerification.Kind.DOCUMENT,
        expires_at=now + timedelta(days=1),
    )
    field = create_verification(
        property_record,
        kind=PropertyVerification.Kind.FIELD,
        expires_at=now + timedelta(days=1),
    )

    assert get_effective_verification_level(user=user, property_record=property_record, at=now) == 2

    field.expires_at = now - timedelta(seconds=1)
    field.save(update_fields=["expires_at", "updated_at"])
    assert get_effective_verification_level(user=user, property_record=property_record, at=now) == 2

    document.expires_at = now - timedelta(seconds=1)
    document.save(update_fields=["expires_at", "updated_at"])
    assert get_effective_verification_level(user=user, property_record=property_record, at=now) == 1

    identity.expires_at = now - timedelta(seconds=1)
    identity.save(update_fields=["expires_at", "updated_at"])
    assert get_effective_verification_level(user=user, property_record=property_record, at=now) == 0


def test_historical_invalid_records_do_not_block_newer_effective_approval():
    user = create_user()
    property_record = create_property(user)
    create_identity(user, expires_at=timezone.now() + timedelta(days=1))
    create_verification(
        property_record,
        kind=PropertyVerification.Kind.DOCUMENT,
        status=PropertyVerification.Status.REJECTED,
    )
    create_verification(property_record, kind=PropertyVerification.Kind.DOCUMENT)

    assert get_effective_verification_level(user=user, property_record=property_record) == 2


def test_query_helper_finds_only_properties_with_current_effective_records():
    user = create_user()
    valid_property = create_property(user)
    invalid_property = create_property(user)
    create_verification(valid_property, kind=PropertyVerification.Kind.DOCUMENT)
    create_verification(
        invalid_property,
        kind=PropertyVerification.Kind.DOCUMENT,
        status=PropertyVerification.Status.REJECTED,
    )

    result_ids = set(
        filter_queryset_with_effective_property_verification(
            PropertyRecord.objects.all(),
            kind=PropertyVerification.Kind.DOCUMENT,
        ).values_list("pk", flat=True)
    )

    assert valid_property.pk in result_ids
    assert invalid_property.pk not in result_ids


@pytest.mark.parametrize("reference", ["https://example.test/evidence", "data:image/png;base64,AAAA", "../private/doc", "/private/doc"])
def test_evidence_references_must_remain_opaque_private_references(reference):
    user = create_user()
    verification = create_verification(create_property(user), kind=PropertyVerification.Kind.DOCUMENT)

    with pytest.raises(DRFValidationError):
        PropertyVerificationEvidence.objects.create(
            verification=verification,
            evidence_type=PropertyVerificationEvidence.EvidenceType.TITLE_DOCUMENT,
            evidence_ref=reference,
            created_by=user,
        )


def test_evidence_uses_normalized_opaque_reference_and_no_verification_level_field_exists():
    user = create_user()
    verification = create_verification(create_property(user), kind=PropertyVerification.Kind.DOCUMENT)
    evidence = PropertyVerificationEvidence.objects.create(
        verification=verification,
        evidence_type=PropertyVerificationEvidence.EvidenceType.TITLE_DOCUMENT,
        evidence_ref="  private/doc-reference  ",
        created_by=user,
    )

    assert evidence.evidence_ref == "private/doc-reference"
    with pytest.raises(FieldDoesNotExist):
        PropertyVerification._meta.get_field("verification_level")
