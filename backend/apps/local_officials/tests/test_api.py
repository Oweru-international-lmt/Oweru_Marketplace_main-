from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.local_officials.audit_events import (
    LOCAL_OFFICIAL_JURISDICTION_ASSIGNED,
    LOCAL_OFFICIAL_JURISDICTION_REVOKED,
    LOCAL_OFFICIAL_PROFILE_CREATED,
    LOCAL_OFFICIAL_PROFILE_DEACTIVATED,
    LOCAL_OFFICIAL_PROFILE_REACTIVATED,
    LOCAL_OFFICIAL_PROFILE_UPDATED,
)
from apps.local_officials.models import OfficialJurisdictionAssignment
from apps.local_officials.services import update_local_official_profile
from apps.roles.catalog import ROLE_LOCAL_OFFICIAL, ROLE_VERIFIER
from apps.roles.models import UserRole

from .test_models_services import create_user, locality_tree, local_official_user, management_actor, profile_for


pytestmark = pytest.mark.django_db


MANAGEMENT_URL = "/api/v1/management/local-officials/"
SELF_URL = "/api/v1/local-official/me/"


def api_client(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


def profile_url(profile):
    return f"{MANAGEMENT_URL}{profile.official_id}/"


def jurisdictions_url(profile):
    return f"{profile_url(profile)}jurisdictions/"


def create_profile_via_api(*, manager, user, official_number="LO-API-001"):
    return api_client(manager).post(
        MANAGEMENT_URL,
        {"user": str(user.pk), "official_number": official_number},
        format="json",
    )


def assignment_payload(*, scope_type, region=None, district=None, ward=None, starts_at=None, expires_at=None):
    payload = {
        "scope_type": scope_type,
        "starts_at": (starts_at or timezone.now() - timedelta(minutes=1)).isoformat(),
    }
    if expires_at is not None:
        payload["expires_at"] = expires_at.isoformat()
    if region is not None:
        payload["region"] = str(region.pk)
    if district is not None:
        payload["district"] = str(district.pk)
    if ward is not None:
        payload["ward"] = str(ward.pk)
    return payload


def test_management_endpoints_require_persisted_management_role():
    manager = management_actor()
    official = local_official_user()
    verifier = create_user("verifier-api@example.test")
    from apps.roles.models import Role

    UserRole.objects.create(user=verifier, role=Role.objects.get(code=ROLE_VERIFIER))
    privileged = create_user("privileged-api@example.test")
    privileged.is_staff = True
    privileged.is_superuser = True
    privileged.save(update_fields=["is_staff", "is_superuser"])

    for user in (None, create_user("ordinary-api@example.test"), official, verifier, privileged):
        response = api_client(user).get(MANAGEMENT_URL)
        assert response.status_code == (401 if user is None else 403)
    assert api_client(manager).get(MANAGEMENT_URL).status_code == 200


def test_management_profile_create_list_detail_patch_and_mass_assignment_protection():
    manager = management_actor()
    official = local_official_user()
    created = create_profile_via_api(manager=manager, user=official, official_number="  LO-API-001 ")
    assert created.status_code == 201
    assert created.data["official_number"] == "LO-API-001"
    assert set(created.data) == {"official_id", "user_id", "official_number", "is_active", "created_at", "updated_at"}
    assert AuditLog.objects.filter(action=LOCAL_OFFICIAL_PROFILE_CREATED).count() == 1

    profile = official.local_official_profile
    no_role = create_profile_via_api(manager=manager, user=create_user("no-role-api@example.test"), official_number="LO-API-NO-ROLE")
    assert no_role.status_code == 400
    assert create_profile_via_api(manager=manager, user=official, official_number="LO-API-DUPLICATE-USER").status_code == 400
    second_official = local_official_user("protected-api@example.test")
    second = create_profile_via_api(manager=manager, user=second_official, official_number="LO-API-002")
    assert second.status_code == 201
    duplicate_number = create_profile_via_api(
        manager=manager,
        user=local_official_user("duplicate-number-api@example.test"),
        official_number="LO-API-001",
    )
    assert duplicate_number.status_code == 400
    protected = api_client(manager).post(
        MANAGEMENT_URL,
        {
            "user": str(local_official_user("protected-two-api@example.test").pk),
            "official_number": "LO-API-PROTECTED",
            "official_id": "OFF-ATTACK",
            "is_active": False,
            "role": "management",
        },
        format="json",
    )
    assert protected.status_code == 400

    listed = api_client(manager).get(f"{MANAGEMENT_URL}?page_size=1")
    assert listed.status_code == 200
    assert listed.data["count"] == 2
    assert len(listed.data["results"]) == 1
    assert [item["official_id"] for item in api_client(manager).get(MANAGEMENT_URL).data["results"]] == sorted(
        profile.official_id for profile in [official.local_official_profile, second_official.local_official_profile]
    )

    detail = api_client(manager).get(profile_url(profile))
    assert detail.status_code == 200
    assert api_client(manager).get(f"{MANAGEMENT_URL}OFF-0000000000000000/").status_code == 404
    assert api_client(manager).patch(profile_url(profile), {"official_number": "LO-API-UPDATED"}, format="json").status_code == 200
    assert AuditLog.objects.filter(action=LOCAL_OFFICIAL_PROFILE_UPDATED).count() == 1
    assert api_client(manager).patch(profile_url(profile), {"is_active": False}, format="json").status_code == 200
    assert AuditLog.objects.filter(action=LOCAL_OFFICIAL_PROFILE_DEACTIVATED).count() == 1
    assert api_client(manager).patch(profile_url(profile), {"is_active": True}, format="json").status_code == 200
    assert AuditLog.objects.filter(action=LOCAL_OFFICIAL_PROFILE_REACTIVATED).count() == 1
    assert api_client(manager).patch(profile_url(profile), {"user": str(manager.pk)}, format="json").status_code == 400
    assert api_client(manager).patch(profile_url(profile), {"official_id": "OFF-ATTACK"}, format="json").status_code == 400
    assert api_client(manager).put(profile_url(profile), {}, format="json").status_code == 405
    assert api_client(manager).delete(profile_url(profile)).status_code == 405


def test_management_jurisdiction_api_uses_services_and_contains_assignments_to_profile_path():
    manager = management_actor()
    profile = profile_for(actor=manager, user=local_official_user(), official_number="LO-API-JUR-001")
    other_profile = profile_for(actor=manager, user=local_official_user("other-jur-api@example.test"), official_number="LO-API-JUR-002")
    region, district, ward, _ = locality_tree("api")

    created = api_client(manager).post(
        jurisdictions_url(profile),
        assignment_payload(scope_type="REGION", region=region),
        format="json",
    )
    assert created.status_code == 201
    assert created.data["area"] == {"id": str(region.pk), "name": region.name}
    assert AuditLog.objects.filter(action=LOCAL_OFFICIAL_JURISDICTION_ASSIGNED).count() == 1
    assignment = profile.jurisdiction_assignments.get()

    for scope_type, area_field, area in (
        ("DISTRICT", "district", district),
        ("WARD", "ward", ward),
    ):
        response = api_client(manager).post(
            jurisdictions_url(profile),
            assignment_payload(scope_type=scope_type, **{area_field: area}),
            format="json",
        )
        assert response.status_code == 201
    invalid = api_client(manager).post(
        jurisdictions_url(profile),
        assignment_payload(scope_type="REGION", region=region, district=district),
        format="json",
    )
    assert invalid.status_code == 400
    protected = api_client(manager).post(
        jurisdictions_url(profile),
        {
            **assignment_payload(scope_type="REGION", region=region),
            "assignment_id": "JUR-ATTACK",
            "status": "REVOKED",
            "assigned_by": str(manager.pk),
            "revoked_by": str(manager.pk),
        },
        format="json",
    )
    assert protected.status_code == 400

    listed = api_client(manager).get(jurisdictions_url(profile))
    assert listed.status_code == 200
    assert listed.data["count"] == 3
    assert all(set(item) == {"assignment_id", "scope_type", "area", "starts_at", "expires_at", "status", "created_at", "revoked_at"} for item in listed.data["results"])

    foreign = api_client(manager).post(
        f"{jurisdictions_url(other_profile)}{assignment.assignment_id}/revoke/",
        {},
        format="json",
    )
    assert foreign.status_code == 404
    revoked = api_client(manager).post(
        f"{jurisdictions_url(profile)}{assignment.assignment_id}/revoke/",
        {},
        format="json",
    )
    assert revoked.status_code == 200
    assert revoked.data["status"] == OfficialJurisdictionAssignment.Status.REVOKED
    assert AuditLog.objects.filter(action=LOCAL_OFFICIAL_JURISDICTION_REVOKED).count() == 1
    assert api_client(manager).post(
        f"{jurisdictions_url(profile)}{assignment.assignment_id}/revoke/",
        {},
        format="json",
    ).status_code == 400


def test_local_official_self_endpoints_are_safe_read_only_and_effective():
    manager = management_actor()
    official = local_official_user()
    profile = profile_for(actor=manager, user=official, official_number="LO-SELF-001")
    region, district, ward, _ = locality_tree("self")
    now = timezone.now()
    active = api_client(manager).post(
        jurisdictions_url(profile),
        assignment_payload(scope_type="WARD", ward=ward, starts_at=now - timedelta(minutes=1)),
        format="json",
    )
    future = api_client(manager).post(
        jurisdictions_url(profile),
        assignment_payload(scope_type="DISTRICT", district=district, starts_at=now + timedelta(days=1)),
        format="json",
    )
    assert active.status_code == future.status_code == 201

    assert api_client().get(SELF_URL).status_code == 401
    assert api_client(create_user("ordinary-self-api@example.test")).get(SELF_URL).status_code == 403
    self_profile = api_client(official).get(SELF_URL)
    assert self_profile.status_code == 200
    assert self_profile.data == {"official_id": profile.official_id, "official_number": "LO-SELF-001", "is_active": True}
    self_assignments = api_client(official).get(f"{SELF_URL}jurisdictions/")
    assert self_assignments.status_code == 200
    effective = {item["assignment_id"]: item["effective"] for item in self_assignments.data["results"]}
    assert effective[active.data["assignment_id"]]
    assert not effective[future.data["assignment_id"]]
    rendered = repr(self_assignments.data)
    for forbidden in ("assigned_by", "revoked_by", "official_number", "email", "phone", "pin", "boundary", "evidence"):
        assert forbidden not in rendered
    assert api_client(official).patch(SELF_URL, {"is_active": False}, format="json").status_code == 405
    assert api_client(official).post(f"{SELF_URL}jurisdictions/", {}, format="json").status_code == 405

    revoked = api_client(manager).post(
        f"{jurisdictions_url(profile)}{active.data['assignment_id']}/revoke/",
        {},
        format="json",
    )
    assert revoked.status_code == 200
    refreshed = api_client(official).get(f"{SELF_URL}jurisdictions/")
    refreshed_effective = {item["assignment_id"]: item["effective"] for item in refreshed.data["results"]}
    assert not refreshed_effective[active.data["assignment_id"]]

    update_local_official_profile(actor=manager, profile=profile, is_active=False)
    assert api_client(official).get(SELF_URL).status_code == 403
    update_local_official_profile(actor=manager, profile=profile, is_active=True)
    role = UserRole.objects.get(user=official, role__code=ROLE_LOCAL_OFFICIAL)
    role.is_active = False
    role.save(update_fields=["is_active"])
    assert api_client(official).get(SELF_URL).status_code == 403
