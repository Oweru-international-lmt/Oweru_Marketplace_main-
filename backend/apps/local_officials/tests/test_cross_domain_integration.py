from datetime import timedelta

import pytest
from django.utils import timezone

from apps.local_officials.queries import get_local_official_field_queue
from apps.local_officials.policies import can_review_field_verification
from apps.local_officials.services import assign_jurisdiction
from apps.properties.services import update_property_record
from apps.verification.models import PropertyVerification
from apps.verification.services import (
    approve_document_verification,
    approve_field_verification,
    get_effective_verification_level,
    submit_document_verification,
    submit_field_verification,
)
from apps.verification.tests.test_document_lifecycle import document_evidence, verifier
from apps.verification.tests.test_field_lifecycle import field_evidence, submitted_field

from .test_field_verification_authorization import official_with_assignment
from .test_models_services import locality_tree


pytestmark = pytest.mark.django_db


def test_locality_renames_do_not_change_fk_based_field_authority():
    _, property_record, _, field = submitted_field()
    reviewer, _, _, _ = official_with_assignment(property_record)

    property_record.region.name = "Renamed Region"
    property_record.region.save(update_fields=["name", "updated_at"])
    property_record.district.name = "Renamed District"
    property_record.district.save(update_fields=["name", "updated_at"])
    property_record.ward.name = "Renamed Ward"
    property_record.ward.save(update_fields=["name", "updated_at"])

    assert can_review_field_verification(reviewer, field)
    assert get_local_official_field_queue(user=reviewer).filter(pk=field.pk).exists()


def test_property_geography_update_invalidates_m14_and_recalculates_m16_review_scope():
    owner, property_record, _, field = submitted_field()
    ward_a_official, _, _, _ = official_with_assignment(property_record)
    approve_field_verification(verification=field, reviewer=ward_a_official)
    assert get_effective_verification_level(user=owner, property_record=property_record) == 3

    region_b, district_b, ward_b, locality_b = locality_tree("m16-cross-domain")
    ward_b_official, manager_b, profile_b, _ = official_with_assignment()
    assign_jurisdiction(
        actor=manager_b,
        official=profile_b,
        scope_type="WARD",
        ward=ward_b,
        starts_at=timezone.now() - timedelta(minutes=1),
    )

    update_property_record(
        actor=owner,
        property_record=property_record,
        region=region_b,
        district=district_b,
        ward=ward_b,
        locality=locality_b,
    )

    property_record.refresh_from_db()
    field.refresh_from_db()
    assert field.status == PropertyVerification.Status.REVOKED
    assert get_effective_verification_level(user=owner, property_record=property_record) == 1
    assert not can_review_field_verification(ward_a_official, field)
    assert can_review_field_verification(ward_b_official, field)

    document = approve_document_verification(
        verification=submit_document_verification(
            property_record=property_record,
            submitted_by=owner,
            evidence=document_evidence("private/cross-domain-document"),
        ),
        reviewer=verifier(),
    )
    assert document.status == PropertyVerification.Status.APPROVED
    replacement = submit_field_verification(
        property_record=property_record,
        submitted_by=owner,
        evidence=field_evidence("private/cross-domain-field"),
    )
    assert not get_local_official_field_queue(user=ward_a_official).filter(pk=replacement.pk).exists()
    assert get_local_official_field_queue(user=ward_b_official).filter(pk=replacement.pk).exists()

    approve_field_verification(verification=replacement, reviewer=ward_b_official)
    assert get_effective_verification_level(user=owner, property_record=property_record) == 3
