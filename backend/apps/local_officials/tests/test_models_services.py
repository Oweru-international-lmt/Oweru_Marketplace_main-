from datetime import timedelta

import pytest
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.local_officials.audit_events import (
    LOCAL_OFFICIAL_JURISDICTION_ASSIGNED,
    LOCAL_OFFICIAL_JURISDICTION_REVOKED,
    LOCAL_OFFICIAL_PROFILE_CREATED,
    LOCAL_OFFICIAL_PROFILE_DEACTIVATED,
    LOCAL_OFFICIAL_PROFILE_REACTIVATED,
    LOCAL_OFFICIAL_PROFILE_UPDATED,
)
from apps.local_officials.models import LocalOfficialProfile, OfficialJurisdictionAssignment
from apps.local_officials.services import (
    assignment_covers_property,
    assign_jurisdiction,
    create_local_official_profile,
    get_effective_jurisdiction_assignments,
    is_effective_jurisdiction_assignment,
    is_effective_local_official,
    revoke_jurisdiction,
    update_local_official_profile,
)
from apps.localities.models import District, Locality, Region, Ward
from apps.properties.models import PropertyRecord
from apps.roles.catalog import ROLE_LOCAL_OFFICIAL, ROLE_MANAGEMENT
from apps.roles.models import Role, UserRole
from apps.roles.services import bootstrap_canonical_roles


pytestmark = pytest.mark.django_db


def create_user(email):
    return User.objects.create_user(
        email=email,
        phone=f"+2557{abs(hash(email)) % 100000000:08d}",
        full_name="Local Official Test User",
        password="Strong-pass-482!",
    )


def grant_role(user, role_code):
    bootstrap_canonical_roles()
    return UserRole.objects.create(user=user, role=Role.objects.get(code=role_code))


def management_actor(email="manager@example.test"):
    actor = create_user(email)
    grant_role(actor, ROLE_MANAGEMENT)
    return actor


def local_official_user(email="official@example.test"):
    user = create_user(email)
    grant_role(user, ROLE_LOCAL_OFFICIAL)
    return user


def locality_tree(suffix="one"):
    region = Region.objects.create(name=f"Region {suffix}")
    district = District.objects.create(region=region, name=f"District {suffix}")
    ward = Ward.objects.create(district=district, name=f"Ward {suffix}")
    locality = Locality.objects.create(
        ward=ward,
        name=f"Village {suffix}",
        kind=Locality.Kind.VILLAGE,
        approved=True,
    )
    return region, district, ward, locality


def profile_for(*, actor=None, user=None, official_number="LO-001"):
    return create_local_official_profile(
        actor=actor or management_actor(),
        user=user or local_official_user(),
        official_number=official_number,
    )


def assign_region(*, actor, profile, region, starts_at=None, expires_at=None):
    return assign_jurisdiction(
        actor=actor,
        official=profile,
        scope_type=OfficialJurisdictionAssignment.ScopeType.REGION,
        region=region,
        starts_at=starts_at or timezone.now() - timedelta(minutes=1),
        expires_at=expires_at,
    )


def test_profile_creation_requires_management_active_local_official_and_records_safe_audit():
    actor = management_actor()
    official = local_official_user()

    profile = profile_for(actor=actor, user=official, official_number="  LO-001  ")

    assert profile.official_id.startswith("OFF-")
    assert len(profile.official_id) == 20
    assert profile.official_number == "LO-001"
    audit = AuditLog.objects.get(action=LOCAL_OFFICIAL_PROFILE_CREATED)
    assert audit.actor_id == actor.pk
    assert audit.entity_id == str(profile.pk)
    assert audit.after == {"official_id": profile.official_id, "is_active": True}
    assert "official_number" not in audit.after

    with pytest.raises(PermissionDenied):
        create_local_official_profile(actor=official, user=official, official_number="LO-002")

    without_role = create_user("without-role@example.test")
    with pytest.raises(ValidationError):
        create_local_official_profile(actor=actor, user=without_role, official_number="LO-003")


def test_profile_integrity_rejects_blank_duplicate_user_and_duplicate_official_number():
    actor = management_actor()
    official = local_official_user()
    profile_for(actor=actor, user=official, official_number="LO-001")

    with pytest.raises(ValidationError):
        create_local_official_profile(actor=actor, user=official, official_number="LO-002")
    with pytest.raises(ValidationError):
        create_local_official_profile(actor=actor, user=local_official_user("two@example.test"), official_number="  ")
    with pytest.raises(ValidationError):
        create_local_official_profile(actor=actor, user=local_official_user("three@example.test"), official_number="LO-001")

    invalid = LocalOfficialProfile(
        official_id="OFF-0000000000000000",
        user=local_official_user("four@example.test"),
        official_number=" ",
    )
    with pytest.raises(DjangoValidationError):
        invalid.full_clean()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            LocalOfficialProfile.objects.create(
                official_id="OFF-0000000000000000",
                user=invalid.user,
                official_number="",
            )


def test_profile_identifier_retries_a_collision(monkeypatch):
    actor = management_actor()
    existing = profile_for(actor=actor, user=local_official_user(), official_number="LO-001")
    identifiers = iter([existing.official_id, "OFF-0123456789ABCDEF"])
    monkeypatch.setattr("apps.local_officials.models._identifier", lambda prefix: next(identifiers))

    profile = profile_for(actor=actor, user=local_official_user("collision@example.test"), official_number="LO-002")

    assert profile.official_id == "OFF-0123456789ABCDEF"


def test_profile_update_deactivation_reactivation_and_noop_have_correct_audits():
    actor = management_actor()
    profile = profile_for(actor=actor, user=local_official_user(), official_number="LO-001")

    updated = update_local_official_profile(actor=actor, profile=profile, official_number="  LO-002 ")
    assert updated.official_number == "LO-002"
    assert AuditLog.objects.filter(action=LOCAL_OFFICIAL_PROFILE_UPDATED).count() == 1

    update_local_official_profile(actor=actor, profile=profile, official_number="LO-002")
    assert AuditLog.objects.filter(action=LOCAL_OFFICIAL_PROFILE_UPDATED).count() == 1

    update_local_official_profile(actor=actor, profile=profile, is_active=False)
    update_local_official_profile(actor=actor, profile=profile, is_active=True)
    assert AuditLog.objects.filter(action=LOCAL_OFFICIAL_PROFILE_DEACTIVATED).count() == 1
    assert AuditLog.objects.filter(action=LOCAL_OFFICIAL_PROFILE_REACTIVATED).count() == 1
    with pytest.raises(ValidationError):
        update_local_official_profile(actor=actor, profile=profile, official_id="OFF-CHANGED")


@pytest.mark.parametrize(
    ("scope_type", "scope_name"),
    [
        (OfficialJurisdictionAssignment.ScopeType.REGION, "region"),
        (OfficialJurisdictionAssignment.ScopeType.DISTRICT, "district"),
        (OfficialJurisdictionAssignment.ScopeType.WARD, "ward"),
    ],
)
def test_assignment_supports_exactly_one_canonical_scope(scope_type, scope_name):
    actor = management_actor()
    profile = profile_for(actor=actor, user=local_official_user())
    region, district, ward, _ = locality_tree()
    values = {"region": None, "district": None, "ward": None}
    values[scope_name] = {"region": region, "district": district, "ward": ward}[scope_name]

    assignment = assign_jurisdiction(
        actor=actor,
        official=profile,
        scope_type=scope_type,
        starts_at=timezone.now() - timedelta(minutes=1),
        **values,
    )

    assert assignment.assignment_id.startswith("JUR-")
    assert len(assignment.assignment_id) == 20
    assert assignment.status == OfficialJurisdictionAssignment.Status.ACTIVE
    assert getattr(assignment, f"{scope_name}_id") is not None
    assert sum(value is not None for value in (assignment.region_id, assignment.district_id, assignment.ward_id)) == 1
    audit = AuditLog.objects.get(action=LOCAL_OFFICIAL_JURISDICTION_ASSIGNED, entity_id=str(assignment.pk))
    assert audit.actor_id == actor.pk
    assert audit.after["scope_type"] == scope_type
    assert audit.after["area_id"] == str(getattr(assignment, f"{scope_name}_id"))
    assert "official_number" not in audit.after


def test_assignment_rejects_invalid_scope_period_and_duplicate_active_scope():
    actor = management_actor()
    profile = profile_for(actor=actor, user=local_official_user())
    region, district, _, _ = locality_tree()
    starts_at = timezone.now()

    with pytest.raises(ValidationError):
        assign_jurisdiction(
            actor=actor,
            official=profile,
            scope_type=OfficialJurisdictionAssignment.ScopeType.REGION,
            region=region,
            district=district,
            starts_at=starts_at,
        )
    with pytest.raises(ValidationError):
        assign_jurisdiction(
            actor=actor,
            official=profile,
            scope_type="UNKNOWN",
            region=region,
            starts_at=starts_at,
        )
    with pytest.raises(ValidationError):
        assign_jurisdiction(
            actor=actor,
            official=profile,
            scope_type=OfficialJurisdictionAssignment.ScopeType.REGION,
            region=region,
            starts_at=starts_at,
            expires_at=starts_at,
        )
    with pytest.raises(ValidationError):
        assign_jurisdiction(
            actor=actor,
            official=profile,
            scope_type=OfficialJurisdictionAssignment.ScopeType.WARD,
            starts_at=starts_at,
        )

    assign_region(actor=actor, profile=profile, region=region, starts_at=starts_at)
    with pytest.raises(ValidationError):
        assign_region(actor=actor, profile=profile, region=region, starts_at=starts_at)


def test_assignment_identifier_retries_collision_and_overlapping_scopes_remain_valid(monkeypatch):
    actor = management_actor()
    profile = profile_for(actor=actor, user=local_official_user())
    region, district, ward, _ = locality_tree()
    existing = assign_region(actor=actor, profile=profile, region=region)
    identifiers = iter([
        existing.assignment_id,
        "JUR-0123456789ABCDEF",
        "JUR-1123456789ABCDEF",
    ])
    monkeypatch.setattr("apps.local_officials.models._identifier", lambda prefix: next(identifiers))

    district_assignment = assign_jurisdiction(
        actor=actor,
        official=profile,
        scope_type=OfficialJurisdictionAssignment.ScopeType.DISTRICT,
        district=district,
        starts_at=timezone.now() - timedelta(minutes=1),
    )
    ward_assignment = assign_jurisdiction(
        actor=actor,
        official=profile,
        scope_type=OfficialJurisdictionAssignment.ScopeType.WARD,
        ward=ward,
        starts_at=timezone.now() - timedelta(minutes=1),
    )

    assert district_assignment.assignment_id == "JUR-0123456789ABCDEF"
    assert ward_assignment.status == OfficialJurisdictionAssignment.Status.ACTIVE
    assert OfficialJurisdictionAssignment.objects.filter(official=profile, status="ACTIVE").count() == 3


def test_revoke_preserves_history_permits_reassignment_and_audits_once():
    actor = management_actor()
    profile = profile_for(actor=actor, user=local_official_user())
    region, _, _, _ = locality_tree()
    assignment = assign_region(actor=actor, profile=profile, region=region)

    revoked = revoke_jurisdiction(actor=actor, assignment=assignment)
    assert revoked.status == OfficialJurisdictionAssignment.Status.REVOKED
    assert revoked.revoked_by_id == actor.pk
    assert revoked.revoked_at is not None
    assert AuditLog.objects.filter(action=LOCAL_OFFICIAL_JURISDICTION_REVOKED).count() == 1
    with pytest.raises(ValidationError):
        revoke_jurisdiction(actor=actor, assignment=assignment)
    assert AuditLog.objects.filter(action=LOCAL_OFFICIAL_JURISDICTION_REVOKED).count() == 1

    replacement = assign_region(actor=actor, profile=profile, region=region)
    assert replacement.pk != assignment.pk
    assert OfficialJurisdictionAssignment.objects.filter(official=profile).count() == 2


def test_effective_official_and_assignments_follow_role_profile_user_and_time_state():
    actor = management_actor()
    official = local_official_user()
    profile = profile_for(actor=actor, user=official)
    region, _, _, _ = locality_tree()
    now = timezone.now()
    future = assign_region(
        actor=actor,
        profile=profile,
        region=region,
        starts_at=now + timedelta(days=1),
        expires_at=now + timedelta(days=2),
    )

    assert is_effective_local_official(official)
    assert not is_effective_jurisdiction_assignment(future, at=now)
    assert is_effective_jurisdiction_assignment(future, at=now + timedelta(days=1, minutes=1))
    assert not is_effective_jurisdiction_assignment(future, at=now + timedelta(days=2, minutes=1))

    role_assignment = UserRole.objects.get(user=official, role__code=ROLE_LOCAL_OFFICIAL)
    role_assignment.is_active = False
    role_assignment.save(update_fields=["is_active"])
    assert not is_effective_local_official(official)
    assert not get_effective_jurisdiction_assignments(user=official).exists()

    role_assignment.is_active = True
    role_assignment.save(update_fields=["is_active"])
    update_local_official_profile(actor=actor, profile=profile, is_active=False)
    assert not is_effective_local_official(official)
    update_local_official_profile(actor=actor, profile=profile, is_active=True)
    assert is_effective_local_official(official)

    official.is_active = False
    official.save(update_fields=["is_active"])
    assert not is_effective_local_official(official)


def test_assignment_coverage_uses_normalized_area_foreign_keys_not_geometry():
    actor = management_actor()
    owner = create_user("property-owner@example.test")
    official = local_official_user()
    profile = profile_for(actor=actor, user=official)
    region, district, ward, locality = locality_tree("covered")
    other_region, other_district, other_ward, _ = locality_tree("other")
    property_record = PropertyRecord.objects.create(
        property_id="PROP-LOCAL-OFFICIAL-1",
        category=PropertyRecord.Category.LAND,
        pin=Point(39.2083, -6.7924, srid=4326),
        region=region,
        district=district,
        ward=ward,
        locality=locality,
        stated_size="1.00",
        size_unit="acre",
        title_type=PropertyRecord.TitleType.UNKNOWN,
        created_by=owner,
    )
    regional = assign_region(actor=actor, profile=profile, region=region)
    nonmatching = assign_region(actor=actor, profile=profile, region=other_region)
    district_assignment = assign_jurisdiction(
        actor=actor,
        official=profile,
        scope_type=OfficialJurisdictionAssignment.ScopeType.DISTRICT,
        district=district,
        starts_at=timezone.now() - timedelta(minutes=1),
    )
    other_district_assignment = assign_jurisdiction(
        actor=actor,
        official=profile,
        scope_type=OfficialJurisdictionAssignment.ScopeType.DISTRICT,
        district=other_district,
        starts_at=timezone.now() - timedelta(minutes=1),
    )
    ward_assignment = assign_jurisdiction(
        actor=actor,
        official=profile,
        scope_type=OfficialJurisdictionAssignment.ScopeType.WARD,
        ward=ward,
        starts_at=timezone.now() - timedelta(minutes=1),
    )
    other_ward_assignment = assign_jurisdiction(
        actor=actor,
        official=profile,
        scope_type=OfficialJurisdictionAssignment.ScopeType.WARD,
        ward=other_ward,
        starts_at=timezone.now() - timedelta(minutes=1),
    )

    assert assignment_covers_property(assignment=regional, property_record=property_record)
    assert assignment_covers_property(assignment=ward_assignment, property_record=property_record)
    assert assignment_covers_property(assignment=district_assignment, property_record=property_record)
    assert not assignment_covers_property(assignment=nonmatching, property_record=property_record)
    assert not assignment_covers_property(assignment=other_district_assignment, property_record=property_record)
    assert not assignment_covers_property(assignment=other_ward_assignment, property_record=property_record)


def test_services_require_management_and_do_not_allow_inactive_profiles_or_roles():
    actor = management_actor()
    ordinary = create_user("ordinary@example.test")
    profile = profile_for(actor=actor, user=local_official_user())
    region, _, _, _ = locality_tree()

    with pytest.raises(PermissionDenied):
        update_local_official_profile(actor=ordinary, profile=profile, is_active=False)
    with pytest.raises(PermissionDenied):
        assign_region(actor=ordinary, profile=profile, region=region)

    update_local_official_profile(actor=actor, profile=profile, is_active=False)
    with pytest.raises(ValidationError):
        assign_region(actor=actor, profile=profile, region=region)

    update_local_official_profile(actor=actor, profile=profile, is_active=True)
    management_assignment = UserRole.objects.get(user=actor, role__code=ROLE_MANAGEMENT)
    management_assignment.is_active = False
    management_assignment.save(update_fields=["is_active"])
    with pytest.raises(PermissionDenied):
        assign_region(actor=actor, profile=profile, region=region)


def test_database_constraints_reject_invalid_direct_assignment_shape():
    actor = management_actor()
    profile = profile_for(actor=actor, user=local_official_user())
    region, _, _, _ = locality_tree()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            OfficialJurisdictionAssignment.objects.create(
                assignment_id="JUR-0000000000000000",
                official=profile,
                scope_type=OfficialJurisdictionAssignment.ScopeType.REGION,
                starts_at=timezone.now(),
                assigned_by=actor,
            )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            OfficialJurisdictionAssignment.objects.create(
                assignment_id="JUR-0000000000000001",
                official=profile,
                scope_type=OfficialJurisdictionAssignment.ScopeType.REGION,
                region=region,
                starts_at=timezone.now(),
                status=OfficialJurisdictionAssignment.Status.REVOKED,
                assigned_by=actor,
            )


def test_audit_failures_roll_back_profile_and_assignment_mutations(monkeypatch):
    actor = management_actor()
    official = local_official_user()
    region, _, _, _ = locality_tree()

    def audit_failure(**kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr("apps.local_officials.services.create_audit_log", audit_failure)
    with pytest.raises(RuntimeError):
        create_local_official_profile(actor=actor, user=official, official_number="LO-001")
    assert not LocalOfficialProfile.objects.filter(user=official).exists()

    monkeypatch.undo()
    profile = profile_for(actor=actor, user=official)
    monkeypatch.setattr("apps.local_officials.services.create_audit_log", audit_failure)
    with pytest.raises(RuntimeError):
        assign_region(actor=actor, profile=profile, region=region)
    assert not OfficialJurisdictionAssignment.objects.filter(official=profile).exists()

    monkeypatch.undo()
    assignment = assign_region(actor=actor, profile=profile, region=region)
    monkeypatch.setattr("apps.local_officials.services.create_audit_log", audit_failure)
    with pytest.raises(RuntimeError):
        update_local_official_profile(actor=actor, profile=profile, official_number="LO-CHANGED")
    profile.refresh_from_db()
    assert profile.official_number == "LO-001"
    with pytest.raises(RuntimeError):
        revoke_jurisdiction(actor=actor, assignment=assignment)
    assignment.refresh_from_db()
    assert assignment.status == OfficialJurisdictionAssignment.Status.ACTIVE
