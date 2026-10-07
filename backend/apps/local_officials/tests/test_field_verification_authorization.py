from datetime import timedelta
from decimal import Decimal
import uuid

import pytest
from django.contrib.gis.geos import Point
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.local_officials.models import OfficialJurisdictionAssignment
from apps.local_officials.policies import can_review_field_verification
from apps.local_officials.queries import get_local_official_field_queue
from apps.local_officials.services import (
    assign_jurisdiction,
    create_local_official_profile,
    revoke_jurisdiction,
    update_local_official_profile,
)
from apps.localities.models import District, Locality, Region, Ward
from apps.properties.models import PropertyRecord
from apps.properties.policies import can_update_property_record, can_view_property_record
from apps.roles.catalog import ROLE_LOCAL_OFFICIAL, ROLE_MANAGEMENT, ROLE_VERIFIER
from apps.roles.models import UserRole
from apps.verification.audit_events import VERIFICATION_FIELD_REJECTED, VERIFICATION_FIELD_REVOKED
from apps.verification.models import PropertyVerification
from apps.verification.services import approve_field_verification, reject_field_verification, revoke_field_verification

from apps.verification.tests.test_document_lifecycle import create_user, grant_role
from apps.verification.tests.test_field_lifecycle import field_evidence, submitted_field


pytestmark = pytest.mark.django_db


def management_actor():
    actor = create_user()
    grant_role(actor, ROLE_MANAGEMENT)
    return actor


def official_with_assignment(property_record=None, *, scope=OfficialJurisdictionAssignment.ScopeType.WARD,
                             starts_at=None, expires_at=None):
    official = create_user()
    grant_role(official, ROLE_LOCAL_OFFICIAL)
    manager = management_actor()
    profile = create_local_official_profile(
        actor=manager,
        user=official,
        official_number=f"LO-{official.pk.hex[:12].upper()}",
    )
    assignment = None
    if property_record is not None:
        area_field = {
            OfficialJurisdictionAssignment.ScopeType.REGION: "region",
            OfficialJurisdictionAssignment.ScopeType.DISTRICT: "district",
            OfficialJurisdictionAssignment.ScopeType.WARD: "ward",
        }[scope]
        assignment = assign_jurisdiction(
            actor=manager,
            official=profile,
            scope_type=scope,
            starts_at=starts_at or timezone.now() - timedelta(minutes=1),
            expires_at=expires_at,
            **{area_field: getattr(property_record, area_field)},
        )
    return official, manager, profile, assignment


def pending_field_for_geography(*, owner, region, district, ward, locality):
    property_record = PropertyRecord.objects.create(
        property_id=f"OWR-{uuid.uuid4().hex[:16].upper()}",
        category=PropertyRecord.Category.LAND,
        pin=Point(39.2083, -6.7924, srid=4326),
        region=region,
        district=district,
        ward=ward,
        locality=locality,
        stated_size=Decimal("100.00"),
        size_unit="sqm",
        title_type=PropertyRecord.TitleType.UNKNOWN,
        created_by=owner,
    )
    return PropertyVerification.objects.create(
        property=property_record,
        kind=PropertyVerification.Kind.FIELD,
        status=PropertyVerification.Status.PENDING,
        submitted_by=owner,
        submitted_at=timezone.now(),
        subject_snapshot={},
    )


def api_client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_policy_requires_persisted_role_profile_assignment_and_rejects_fake_authority():
    _, property_record, _, field = submitted_field()
    role_only = create_user()
    grant_role(role_only, ROLE_LOCAL_OFFICIAL)
    profile_only, _, _, _ = official_with_assignment()

    assert not can_review_field_verification(role_only, field)
    assert not can_review_field_verification(profile_only, field)

    reviewer, _, _, _ = official_with_assignment(property_record)
    assert can_review_field_verification(reviewer, field)

    for user, role in ((create_user(), ROLE_MANAGEMENT), (create_user(), ROLE_VERIFIER)):
        grant_role(user, role)
        user.role = ROLE_LOCAL_OFFICIAL
        user.jwt_claim = ROLE_LOCAL_OFFICIAL
        user.is_staff = True
        user.is_superuser = True
        user.save(update_fields=["is_staff", "is_superuser"])
        assert not can_review_field_verification(user, field)


@pytest.mark.parametrize(
    "scope",
    [
        OfficialJurisdictionAssignment.ScopeType.REGION,
        OfficialJurisdictionAssignment.ScopeType.DISTRICT,
        OfficialJurisdictionAssignment.ScopeType.WARD,
    ],
)
def test_policy_uses_exact_current_region_district_and_ward_ids(scope):
    owner = create_user()
    region = Region.objects.create(name=f"Policy Region {scope}")
    district = District.objects.create(region=region, name=f"Policy District {scope}")
    ward = Ward.objects.create(district=district, name=f"Policy Ward {scope}")
    locality = Locality.objects.create(ward=ward, name=f"Policy Locality {scope}", kind=Locality.Kind.STREET, approved=True)
    field = pending_field_for_geography(
        owner=owner,
        region=region,
        district=district,
        ward=ward,
        locality=locality,
    )
    reviewer, _, _, _ = official_with_assignment(field.property, scope=scope)
    assert can_review_field_verification(reviewer, field)

    if scope == OfficialJurisdictionAssignment.ScopeType.REGION:
        other_region = Region.objects.create(name=f"Other Region {scope}")
        other_district = District.objects.create(region=other_region, name=f"Other District {scope}")
        other_ward = Ward.objects.create(district=other_district, name=f"Other Ward {scope}")
    elif scope == OfficialJurisdictionAssignment.ScopeType.DISTRICT:
        other_region = region
        other_district = District.objects.create(region=region, name=f"Sibling District {scope}")
        other_ward = Ward.objects.create(district=other_district, name=f"Other Ward {scope}")
    else:
        other_region = region
        other_district = district
        other_ward = Ward.objects.create(district=district, name=f"Sibling Ward {scope}")
    other_locality = Locality.objects.create(
        ward=other_ward,
        name=f"Other Locality {scope}",
        kind=Locality.Kind.STREET,
        approved=True,
    )
    other_field = pending_field_for_geography(
        owner=owner,
        region=other_region,
        district=other_district,
        ward=other_ward,
        locality=other_locality,
    )
    assert not can_review_field_verification(reviewer, other_field)


def test_policy_handles_any_matching_assignment_and_time_boundaries():
    _, property_record, _, field = submitted_field()
    reviewer, manager, profile, assignment = official_with_assignment(property_record)
    assert can_review_field_verification(reviewer, field)

    other_region = Region.objects.create(name="Additional Region")
    assign_jurisdiction(
        actor=manager,
        official=profile,
        scope_type=OfficialJurisdictionAssignment.ScopeType.REGION,
        region=other_region,
        starts_at=timezone.now() - timedelta(minutes=1),
    )
    assert can_review_field_verification(reviewer, field)

    revoke_jurisdiction(actor=manager, assignment=assignment)
    assert not can_review_field_verification(reviewer, field)

    now = timezone.now()
    future_reviewer, _, _, _ = official_with_assignment(
        property_record,
        starts_at=now + timedelta(hours=1),
        expires_at=now + timedelta(hours=2),
    )
    assert not can_review_field_verification(future_reviewer, field, at=now)
    assert can_review_field_verification(future_reviewer, field, at=now + timedelta(hours=1))
    assert not can_review_field_verification(future_reviewer, field, at=now + timedelta(hours=2))


def test_policy_reflects_profile_role_user_and_current_property_geography_changes():
    _, property_record, _, field = submitted_field()
    reviewer, manager, profile, _ = official_with_assignment(property_record)
    assert can_review_field_verification(reviewer, field)

    update_local_official_profile(actor=manager, profile=profile, is_active=False)
    assert not can_review_field_verification(reviewer, field)
    update_local_official_profile(actor=manager, profile=profile, is_active=True)
    assert can_review_field_verification(reviewer, field)

    role = UserRole.objects.get(user=reviewer, role__code=ROLE_LOCAL_OFFICIAL)
    role.is_active = False
    role.save(update_fields=["is_active"])
    assert not can_review_field_verification(reviewer, field)
    role.is_active = True
    role.save(update_fields=["is_active"])
    assert can_review_field_verification(reviewer, field)

    canonical_role = role.role
    canonical_role.is_active = False
    canonical_role.save(update_fields=["is_active", "updated_at"])
    assert not can_review_field_verification(reviewer, field)
    canonical_role.is_active = True
    canonical_role.save(update_fields=["is_active", "updated_at"])
    assert can_review_field_verification(reviewer, field)

    property_record.region = Region.objects.create(name="Moved Region")
    property_record.district = District.objects.create(region=property_record.region, name="Moved District")
    property_record.ward = Ward.objects.create(district=property_record.district, name="Moved Ward")
    property_record.locality = Locality.objects.create(
        ward=property_record.ward,
        name="Moved Locality",
        kind=Locality.Kind.STREET,
        approved=True,
    )
    property_record.save(update_fields=["region", "district", "ward", "locality", "updated_at"])
    assert not can_review_field_verification(reviewer, field)

    moved_reviewer, _, _, _ = official_with_assignment(property_record)
    assert can_review_field_verification(moved_reviewer, field)
    reviewer.is_active = False
    reviewer.save(update_fields=["is_active"])
    assert not can_review_field_verification(reviewer, field)


def test_field_actions_recheck_scope_and_failed_authorization_creates_no_success_audit():
    _, property_record, _, field = submitted_field()
    authorized, _, _, _ = official_with_assignment(property_record)
    approved = approve_field_verification(verification=field, reviewer=authorized)
    assert approved.status == PropertyVerification.Status.APPROVED

    owner, cross_property, _, cross_field = submitted_field()
    wrong_reviewer, _, _, _ = official_with_assignment(property_record)
    before = AuditLog.objects.filter(action=VERIFICATION_FIELD_REJECTED).count()
    with pytest.raises(PermissionDenied):
        reject_field_verification(verification=cross_field, reviewer=wrong_reviewer, reason="Out of jurisdiction")
    cross_field.refresh_from_db()
    assert cross_field.status == PropertyVerification.Status.PENDING
    assert AuditLog.objects.filter(action=VERIFICATION_FIELD_REJECTED).count() == before

    cross_authorized, _, _, _ = official_with_assignment(cross_property)
    approve_field_verification(verification=cross_field, reviewer=cross_authorized)
    revoked_before = AuditLog.objects.filter(action=VERIFICATION_FIELD_REVOKED).count()
    with pytest.raises(PermissionDenied):
        revoke_field_verification(verification=cross_field, reviewer=wrong_reviewer)
    cross_field.refresh_from_db()
    assert cross_field.status == PropertyVerification.Status.APPROVED
    assert AuditLog.objects.filter(action=VERIFICATION_FIELD_REVOKED).count() == revoked_before
    assert owner.is_active


def test_private_field_views_filter_queue_and_recheck_detail_authorization():
    _, property_record, _, field = submitted_field()
    authorized, _, _, _ = official_with_assignment(property_record)
    role_only = create_user()
    grant_role(role_only, ROLE_LOCAL_OFFICIAL)
    wrong_reviewer, _, _, _ = official_with_assignment(None)
    other_region = Region.objects.create(name="Queue Other Region")
    assign_jurisdiction(
        actor=management_actor(),
        official=wrong_reviewer.local_official_profile,
        scope_type=OfficialJurisdictionAssignment.ScopeType.REGION,
        region=other_region,
        starts_at=timezone.now() - timedelta(minutes=1),
    )

    detail_url = f"/api/v1/management/verifications/field/{field.pk}/"
    queue_url = "/api/v1/management/verifications/field/"
    assert api_client(role_only).get(queue_url).status_code == 403
    assert api_client(wrong_reviewer).get(queue_url).data["count"] == 0
    assert api_client(wrong_reviewer).get(detail_url).status_code == 403
    assert api_client(authorized).get(detail_url).status_code == 200

    assert not can_view_property_record(authorized, property_record)
    assert not can_update_property_record(authorized, property_record)


def test_canonical_field_queue_and_detail_are_scoped_paginated_and_private():
    _, property_record, _, field = submitted_field()
    authorized, _, _, _ = official_with_assignment(property_record)
    _, _, _, other_field = submitted_field()
    role_only = create_user()
    grant_role(role_only, ROLE_LOCAL_OFFICIAL)

    queue_url = "/api/v1/local-official/verifications/field/"
    detail_url = f"{queue_url}{field.pk}/"
    assert api_client(role_only).get(queue_url).status_code == 403

    queue = api_client(authorized).get(queue_url)
    assert queue.status_code == 200
    assert queue.data["count"] == 1
    item = queue.data["results"][0]
    assert item["verification_id"] == str(field.pk)
    assert item["property_id"] == property_record.property_id
    assert set(item) == {
        "verification_id", "kind", "status", "submitted_at", "property_id", "region", "district", "ward",
    }
    assert item["region"] == {"id": str(property_record.region_id), "name": property_record.region.name}
    rendered = repr(queue.data)
    for forbidden in (
        "pin", "boundary", "evidence", "captured_location", "file_key", "file_hash", "official_number",
        "assignment_id", "email", "phone", "site_capture",
    ):
        assert forbidden not in rendered

    assert api_client(authorized).get(detail_url).status_code == 200
    assert api_client(authorized).get(f"{queue_url}{other_field.pk}/").status_code == 403
    assert api_client(authorized).get(f"{queue_url}?page_size=500").status_code == 200


def test_canonical_queue_updates_with_assignment_and_property_changes_and_actions_delegate():
    _, property_record, _, field = submitted_field()
    reviewer, manager, profile, assignment = official_with_assignment(property_record)
    queue_url = "/api/v1/local-official/verifications/field/"
    assert api_client(reviewer).get(queue_url).data["count"] == 1

    revoke_jurisdiction(actor=manager, assignment=assignment)
    assert api_client(reviewer).get(queue_url).status_code == 403
    replacement = assign_jurisdiction(
        actor=manager,
        official=profile,
        scope_type=OfficialJurisdictionAssignment.ScopeType.WARD,
        ward=property_record.ward,
        starts_at=timezone.now() - timedelta(minutes=1),
    )
    assert api_client(reviewer).get(queue_url).data["count"] == 1

    update_local_official_profile(actor=manager, profile=profile, is_active=False)
    assert api_client(reviewer).get(queue_url).status_code == 403
    update_local_official_profile(actor=manager, profile=profile, is_active=True)
    role_assignment = UserRole.objects.get(user=reviewer, role__code=ROLE_LOCAL_OFFICIAL)
    role_assignment.is_active = False
    role_assignment.save(update_fields=["is_active"])
    assert api_client(reviewer).get(queue_url).status_code == 403
    role_assignment.is_active = True
    role_assignment.save(update_fields=["is_active"])
    assert api_client(reviewer).get(queue_url).data["count"] == 1

    approve = api_client(reviewer).post(f"{queue_url}{field.pk}/approve/", {}, format="json")
    assert approve.status_code == 200
    assert approve.data["verification_id"] == str(field.pk)
    assert approve.data["status"] == PropertyVerification.Status.APPROVED

    revoke_jurisdiction(actor=manager, assignment=replacement)
    assert api_client(reviewer).get(f"{queue_url}{field.pk}/").status_code == 403


def test_canonical_queue_query_count_is_bounded_as_rows_grow():
    owner, property_record, _, _ = submitted_field()
    reviewer, _, _, _ = official_with_assignment(property_record)

    with CaptureQueriesContext(connection) as small_context:
        list(get_local_official_field_queue(user=reviewer))

    for _ in range(25):
        pending_field_for_geography(
            owner=owner,
            region=property_record.region,
            district=property_record.district,
            ward=property_record.ward,
            locality=property_record.locality,
        )
    with CaptureQueriesContext(connection) as large_context:
        queue = list(get_local_official_field_queue(user=reviewer))

    assert len(queue) == 26
    assert len(large_context) <= len(small_context) + 1
    assert [item.pk for item in queue] == list(
        get_local_official_field_queue(user=reviewer).values_list("pk", flat=True)
    )
