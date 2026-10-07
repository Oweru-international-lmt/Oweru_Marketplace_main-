from datetime import timedelta

import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.local_officials.models import OfficialJurisdictionAssignment
from apps.local_officials.policies import can_review_field_verification
from apps.local_officials.services import assign_jurisdiction, revoke_jurisdiction
from apps.properties.services import get_property_record
from apps.site_capture.models import SiteCapture
from apps.site_capture.services import get_property_site_captures, get_site_capture, submit_site_capture
from apps.verification.services import approve_document_verification

from .test_api import (
    MANAGEMENT_URL,
    SELF_URL,
    api_client,
    assignment_payload,
    jurisdictions_url,
    profile_url,
)
from .test_field_verification_authorization import official_with_assignment
from .test_models_services import create_user, locality_tree, local_official_user, management_actor, profile_for
from apps.verification.tests.test_field_lifecycle import submitted_field


pytestmark = pytest.mark.django_db


def test_management_authority_cannot_be_spoofed_and_malformed_identifiers_are_safe():
    attacker = create_user("spoofed-local-official@example.test")
    attacker.role = "MANAGEMENT"
    attacker.roles = ["MANAGEMENT", "LOCAL_OFFICIAL"]
    attacker.jwt_claim = {"role": "MANAGEMENT"}
    attacker.permission = "manage_local_officials"
    attacker.is_staff = True
    attacker.is_superuser = True
    attacker.save(update_fields=["is_staff", "is_superuser"])

    assert api_client(attacker).get(MANAGEMENT_URL).status_code == 403
    assert api_client(attacker).post(
        MANAGEMENT_URL,
        {"user": str(attacker.pk), "official_number": "LO-SPOOFED"},
        format="json",
    ).status_code == 403

    manager = management_actor("safe-id-manager@example.test")
    for official_id in ("not-an-official-id", "OFF-0000000000000000"):
        assert api_client(manager).get(f"{MANAGEMENT_URL}{official_id}/").status_code == 404
        assert api_client(manager).get(f"{MANAGEMENT_URL}{official_id}/jurisdictions/").status_code == 404
    assert api_client(manager).post(
        f"{MANAGEMENT_URL}not-an-official-id/jurisdictions/not-an-assignment-id/revoke/",
        {},
        format="json",
    ).status_code == 404


def test_management_write_serializers_reject_full_protected_payloads_and_area_spoofing():
    manager = management_actor("strict-manager@example.test")
    profile = profile_for(
        actor=manager,
        user=local_official_user("strict-official@example.test"),
        official_number="LO-STRICT",
    )
    region, district, ward, locality = locality_tree("strict")
    start = timezone.now() - timedelta(minutes=1)

    profile_attack = {
        "official_number": "LO-ATTACK",
        "official_id": "OFF-ATTACK",
        "user": str(manager.pk),
        "role": "MANAGEMENT",
        "permissions": ["all"],
        "created_at": start.isoformat(),
        "updated_at": start.isoformat(),
        "jurisdiction": "REGION",
        "verification_level": 3,
        "assigned_by": str(manager.pk),
    }
    assert api_client(manager).patch(profile_url(profile), profile_attack, format="json").status_code == 400
    profile.refresh_from_db()
    assert profile.official_number == "LO-STRICT"

    base = assignment_payload(scope_type="REGION", region=region, starts_at=start)
    for field, value in {
        "assignment_id": "JUR-ATTACK",
        "official": str(profile.pk),
        "status": "REVOKED",
        "assigned_by": str(manager.pk),
        "revoked_by": str(manager.pk),
        "revoked_at": start.isoformat(),
        "created_at": start.isoformat(),
        "updated_at": start.isoformat(),
        "effective": True,
        "role": "MANAGEMENT",
        "verification_level": 3,
        "locality": str(locality.pk),
        "coordinates": [39.2, -6.8],
        "polygon": {"type": "Polygon", "coordinates": []},
    }.items():
        response = api_client(manager).post(jurisdictions_url(profile), {**base, field: value}, format="json")
        assert response.status_code == 400, field

    assert api_client(manager).post(
        jurisdictions_url(profile),
        {**base, "district": str(district.pk), "ward": str(ward.pk)},
        format="json",
    ).status_code == 400
    assert OfficialJurisdictionAssignment.objects.filter(official=profile).count() == 0


def test_overlapping_coverage_remains_authoritative_after_narrow_assignment_revocation():
    _, property_record, _, field = submitted_field()
    reviewer, manager, profile, ward_assignment = official_with_assignment(property_record)
    assign_jurisdiction(
        actor=manager,
        official=profile,
        scope_type=OfficialJurisdictionAssignment.ScopeType.REGION,
        region=property_record.region,
        starts_at=timezone.now() - timedelta(minutes=1),
    )

    revoke_jurisdiction(actor=manager, assignment=ward_assignment)

    assert can_review_field_verification(reviewer, field)
    response = api_client(reviewer).post(
        f"/api/v1/local-official/verifications/field/{field.pk}/approve/",
        {},
        format="json",
    )
    assert response.status_code == 200


def test_jurisdiction_does_not_grant_property_site_capture_or_document_access():
    owner, property_record, document, _ = submitted_field()
    official, _, _, _ = official_with_assignment(property_record)
    capture = SiteCapture.objects.create(
        capture_id="CAP-SECURITY-000001",
        property=property_record,
        captured_by=owner,
        captured_at=timezone.now(),
        observed_point=Point(39.25, -6.79, srid=4326),
    )

    assert api_client(official).get(f"/api/v1/properties/{property_record.property_id}/").status_code == 403
    assert api_client(official).patch(
        f"/api/v1/properties/{property_record.property_id}/",
        {"stated_size": "999"},
        format="json",
    ).status_code == 403
    assert api_client(official).get(
        f"/api/v1/properties/{property_record.property_id}/site-captures/"
    ).status_code == 403
    assert api_client(official).get(f"/api/v1/site-captures/{capture.capture_id}/").status_code == 403
    assert api_client(official).post(f"/api/v1/site-captures/{capture.capture_id}/submit/", {}, format="json").status_code == 403

    with pytest.raises(PermissionDenied):
        get_property_record(actor=official, property_id=property_record.property_id)
    with pytest.raises(PermissionDenied):
        get_property_site_captures(actor=official, property_record=property_record)
    with pytest.raises(PermissionDenied):
        get_site_capture(actor=official, capture_id=capture.capture_id)
    with pytest.raises(PermissionDenied):
        submit_site_capture(site_capture=capture, actor=official)
    with pytest.raises(PermissionDenied):
        approve_document_verification(verification=document, reviewer=official)


def test_local_official_list_endpoints_are_bounded_read_only_and_self_scoped():
    manager = management_actor("pagination-manager@example.test")
    official = local_official_user("pagination-official@example.test")
    profile = profile_for(actor=manager, user=official, official_number="LO-PAGINATION")
    region, _, _, _ = locality_tree("pagination")
    assignment = assign_jurisdiction(
        actor=manager,
        official=profile,
        scope_type=OfficialJurisdictionAssignment.ScopeType.REGION,
        region=region,
        starts_at=timezone.now() - timedelta(minutes=1),
    )

    for page_size in ("1000", "0", "-1", "invalid"):
        response = api_client(manager).get(f"{MANAGEMENT_URL}?page_size={page_size}&ordering=email&user={official.pk}")
        assert response.status_code == 200
        assert len(response.data["results"]) <= 100
        response = api_client(official).get(
            f"{SELF_URL}jurisdictions/?page_size={page_size}&official_id=OFF-OTHER&assignment_id={assignment.assignment_id}"
        )
        assert response.status_code == 200
        assert {item["assignment_id"] for item in response.data["results"]} == {assignment.assignment_id}

    assert api_client(manager).put(MANAGEMENT_URL, {}, format="json").status_code == 405
    assert api_client(official).delete(SELF_URL).status_code == 405
