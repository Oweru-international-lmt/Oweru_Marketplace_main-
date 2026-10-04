from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.gis.geos import Point
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.localities.models import Locality, Region, District, Ward
from apps.properties.models import PropertyRecord
from apps.properties.policies import (
    can_create_property_record,
    can_update_property_record,
    can_view_property_record,
    get_accessible_property_records,
)
from apps.properties.services import create_property_record, get_property_record, update_property_record
from apps.roles.catalog import (
    ROLE_AGENT,
    ROLE_BUYER,
    ROLE_LOCAL_OFFICIAL,
    ROLE_MANAGEMENT,
    ROLE_MARKETER,
    ROLE_OWNER,
    ROLE_PROFESSIONAL,
    ROLE_VERIFIER,
)
from apps.roles.models import Role, UserRole
from apps.roles.services import bootstrap_canonical_roles


pytestmark = pytest.mark.django_db


def create_user(email, *, is_active=True):
    return get_user_model().objects.create_user(
        email=email,
        phone=f"+255{abs(hash(email)) % 1000000000:09d}",
        full_name="Property Auth User",
        password="StrongPass123!",
        is_active=is_active,
    )


def grant_role(user, role_code, *, is_active=True, role_active=True):
    bootstrap_canonical_roles()
    role = Role.objects.get(code=role_code)
    role.is_active = role_active
    role.save(update_fields=["is_active"])
    return UserRole.objects.create(user=user, role=role, is_active=is_active)


def create_hierarchy(prefix):
    region = Region.objects.create(name=f"{prefix} Region")
    district = District.objects.create(region=region, name=f"{prefix} District")
    ward = Ward.objects.create(district=district, name=f"{prefix} Ward")
    locality = Locality.objects.create(ward=ward, name=f"{prefix} Street", kind=Locality.Kind.STREET)
    return region, district, ward, locality


def valid_attrs(prefix="Auth"):
    region, district, ward, locality = create_hierarchy(prefix)
    return {
        "category": PropertyRecord.Category.LAND,
        "pin": Point(39.2083, -6.7924, srid=4326),
        "boundary": None,
        "region": region,
        "district": district,
        "ward": ward,
        "locality": locality,
        "stated_size": Decimal("1200.50"),
        "size_unit": "sqm",
        "title_type": PropertyRecord.TitleType.UNKNOWN,
    }


def typed_attrs(prefix="TypedAuth", name="New Auth Street"):
    attrs = valid_attrs(prefix)
    attrs.pop("locality")
    attrs["locality_name"] = name
    attrs["locality_kind"] = Locality.Kind.STREET
    return attrs


def user_with_role(email, role_code, **kwargs):
    user = create_user(email, is_active=kwargs.pop("is_active", True))
    grant_role(user, role_code, **kwargs)
    return user


def create_record_for(user, prefix="Owned"):
    return create_property_record(actor=user, **valid_attrs(prefix))


@pytest.mark.parametrize("role_code", [ROLE_OWNER, ROLE_AGENT])
def test_create_policy_allows_active_owner_or_agent(role_code):
    actor = user_with_role(f"create-{role_code}@example.test", role_code)

    assert can_create_property_record(actor) is True
    assert create_property_record(actor=actor, **valid_attrs(f"Create{role_code}")).created_by == actor


def test_create_policy_allows_owner_plus_agent():
    actor = user_with_role("owner-agent@example.test", ROLE_OWNER)
    grant_role(actor, ROLE_AGENT)

    assert can_create_property_record(actor) is True
    assert create_property_record(actor=actor, **valid_attrs("OwnerAgent")).created_by == actor


@pytest.mark.parametrize(
    "role_code",
    [ROLE_BUYER, ROLE_MANAGEMENT, ROLE_VERIFIER, ROLE_MARKETER, ROLE_PROFESSIONAL, ROLE_LOCAL_OFFICIAL],
)
def test_create_policy_denies_non_lister_roles(role_code):
    actor = user_with_role(f"deny-create-{role_code}@example.test", role_code)

    assert can_create_property_record(actor) is False
    with pytest.raises(PermissionDenied):
        create_property_record(actor=actor, **valid_attrs(f"DenyCreate{role_code}"))


def test_create_policy_denies_anonymous_unsaved_inactive_and_inactive_role_states():
    assert can_create_property_record(AnonymousUser()) is False
    with pytest.raises(PermissionDenied):
        create_property_record(actor=AnonymousUser(), **valid_attrs("AnonCreate"))

    unsaved = get_user_model()(email="unsaved-create@example.test")
    assert can_create_property_record(unsaved) is False

    inactive = user_with_role("inactive-create@example.test", ROLE_OWNER, is_active=False)
    assert can_create_property_record(inactive) is False

    inactive_assignment = user_with_role("inactive-assignment-create@example.test", ROLE_OWNER, is_active=False)
    assert can_create_property_record(inactive_assignment) is False

    inactive_owner_role = user_with_role("inactive-owner-role@example.test", ROLE_OWNER, role_active=False)
    assert can_create_property_record(inactive_owner_role) is False

    Role.objects.filter(code=ROLE_OWNER).update(is_active=True)
    inactive_agent_role = user_with_role("inactive-agent-role@example.test", ROLE_AGENT, role_active=False)
    assert can_create_property_record(inactive_agent_role) is False


def test_creator_can_read_and_update_after_lister_role_removal():
    creator = user_with_role("creator-role-removed@example.test", ROLE_OWNER)
    record = create_record_for(creator, "CreatorRoleRemoved")
    UserRole.objects.filter(user=creator).update(is_active=False)

    assert can_view_property_record(creator, record) is True
    assert can_update_property_record(creator, record) is True
    assert get_property_record(actor=creator, property_id=record.property_id) == record
    assert update_property_record(actor=creator, property_record=record, category=PropertyRecord.Category.HOUSE).category == PropertyRecord.Category.HOUSE


def test_inactive_creator_cannot_read_or_update_own_record():
    creator = user_with_role("inactive-own@example.test", ROLE_OWNER)
    record = create_record_for(creator, "InactiveOwn")
    creator.is_active = False
    creator.save(update_fields=["is_active"])

    assert can_view_property_record(creator, record) is False
    assert can_update_property_record(creator, record) is False
    with pytest.raises(PermissionDenied):
        get_property_record(actor=creator, property_id=record.property_id)
    with pytest.raises(PermissionDenied):
        update_property_record(actor=creator, property_record=record, category=PropertyRecord.Category.HOUSE)


@pytest.mark.parametrize("role_code", [ROLE_OWNER, ROLE_AGENT, ROLE_BUYER, ROLE_VERIFIER])
def test_unrelated_roles_cannot_read_or_update_other_records(role_code):
    creator = user_with_role(f"owner-for-{role_code}@example.test", ROLE_OWNER)
    other = user_with_role(f"other-{role_code}@example.test", role_code)
    if role_code == ROLE_OWNER:
        other.email = other.email
    record = create_record_for(creator, f"Other{role_code}")

    assert can_view_property_record(other, record) is False
    assert can_update_property_record(other, record) is False
    with pytest.raises(PermissionDenied):
        get_property_record(actor=other, property_id=record.property_id)
    with pytest.raises(PermissionDenied):
        update_property_record(actor=other, property_record=record, category=PropertyRecord.Category.COMMERCIAL)


def test_unrelated_user_with_owner_and_agent_still_cannot_access_other_records():
    creator = user_with_role("owner-agent-target@example.test", ROLE_OWNER)
    other = user_with_role("owner-agent-other@example.test", ROLE_OWNER)
    grant_role(other, ROLE_AGENT)
    record = create_record_for(creator, "OwnerAgentOther")

    assert can_view_property_record(other, record) is False
    with pytest.raises(PermissionDenied):
        update_property_record(actor=other, property_record=record, category=PropertyRecord.Category.HOUSE)


def test_active_management_can_read_and_update_any_record_but_cannot_rewrite_identity_fields():
    creator = user_with_role("management-target@example.test", ROLE_OWNER)
    management = user_with_role("management@example.test", ROLE_MANAGEMENT)
    record = create_record_for(creator, "ManagementOverride")
    original_property_id = record.property_id
    original_created_by = record.created_by

    assert can_view_property_record(management, record) is True
    assert can_update_property_record(management, record) is True
    assert get_property_record(actor=management, property_id=record.property_id) == record
    update_property_record(actor=management, property_record=record, category=PropertyRecord.Category.HOUSE)

    with pytest.raises(ValidationError):
        update_property_record(
            actor=management,
            property_record=record,
            property_id="OWR-CLIENT-CHANGE",
            created_by=management,
        )

    record.refresh_from_db()
    assert record.property_id == original_property_id
    assert record.created_by == original_created_by


def test_inactive_or_revoked_management_cannot_override():
    creator = user_with_role("revoked-management-target@example.test", ROLE_OWNER)
    record = create_record_for(creator, "RevokedManagement")

    inactive_management = user_with_role("inactive-management@example.test", ROLE_MANAGEMENT, is_active=False)
    revoked_management = user_with_role("revoked-management@example.test", ROLE_MANAGEMENT)
    UserRole.objects.filter(user=revoked_management, role__code=ROLE_MANAGEMENT).update(is_active=False)
    inactive_role_management = user_with_role("inactive-role-management@example.test", ROLE_MANAGEMENT, role_active=False)

    for actor in (inactive_management, revoked_management, inactive_role_management):
        assert can_view_property_record(actor, record) is False
        with pytest.raises(PermissionDenied):
            update_property_record(actor=actor, property_record=record, category=PropertyRecord.Category.HOUSE)


def test_role_revocation_immediately_affects_create_and_management_override():
    creator = user_with_role("revocation-owner@example.test", ROLE_OWNER)
    record = create_record_for(creator, "Revocation")
    UserRole.objects.filter(user=creator, role__code=ROLE_OWNER).update(is_active=False)

    with pytest.raises(PermissionDenied):
        create_property_record(actor=creator, **valid_attrs("RevocationCreateDenied"))

    management = user_with_role("revocation-management@example.test", ROLE_MANAGEMENT)
    UserRole.objects.filter(user=management, role__code=ROLE_MANAGEMENT).update(is_active=False)
    with pytest.raises(PermissionDenied):
        get_property_record(actor=management, property_id=record.property_id)


def test_query_visibility_helper_is_private_not_role_wide():
    owner = user_with_role("visibility-owner@example.test", ROLE_OWNER)
    agent = user_with_role("visibility-agent@example.test", ROLE_AGENT)
    management = user_with_role("visibility-management@example.test", ROLE_MANAGEMENT)
    owner_record = create_record_for(owner, "VisibilityOwner")
    agent_record = create_record_for(agent, "VisibilityAgent")

    assert list(get_accessible_property_records(owner)) == [owner_record]
    assert list(get_accessible_property_records(agent)) == [agent_record]
    assert set(get_accessible_property_records(management)) == {owner_record, agent_record}

    management.is_active = False
    management.save(update_fields=["is_active"])
    assert list(get_accessible_property_records(management)) == []
    assert list(get_accessible_property_records(AnonymousUser())) == []


def test_client_role_spoofing_does_not_expand_property_access():
    buyer = user_with_role("spoof-buyer@example.test", ROLE_BUYER)
    buyer.role = ROLE_OWNER
    buyer.roles = [ROLE_OWNER, ROLE_MANAGEMENT]
    buyer.claims = {"roles": [ROLE_OWNER, ROLE_MANAGEMENT]}

    with pytest.raises(PermissionDenied):
        create_property_record(actor=buyer, **valid_attrs("SpoofCreate"))

    creator = user_with_role("spoof-target@example.test", ROLE_OWNER)
    record = create_record_for(creator, "SpoofTarget")
    owner = user_with_role("spoof-owner@example.test", ROLE_OWNER)
    owner.role = ROLE_MANAGEMENT
    owner.claims = {"roles": [ROLE_MANAGEMENT]}

    assert can_update_property_record(owner, record) is False
    with pytest.raises(PermissionDenied):
        update_property_record(actor=owner, property_record=record, category=PropertyRecord.Category.HOUSE)


def test_fake_actor_objects_fail_closed():
    class FakeActor:
        is_authenticated = True
        is_active = True
        pk = "not-a-real-user"
        role = ROLE_OWNER

    assert can_create_property_record(FakeActor()) is False
    assert list(get_accessible_property_records(FakeActor())) == []
    with pytest.raises(PermissionDenied):
        create_property_record(actor=FakeActor(), **valid_attrs("FakeActor"))


def test_unauthorized_typed_create_or_update_leaves_no_locality_or_property_side_effects():
    buyer = user_with_role("side-effect-buyer@example.test", ROLE_BUYER)
    attrs = valid_attrs("SideEffectCreate")
    attrs.pop("locality")
    attrs["locality_name"] = "Unauthorized New Street"
    attrs["locality_kind"] = Locality.Kind.STREET

    with pytest.raises(PermissionDenied):
        create_property_record(actor=buyer, **attrs)

    assert not PropertyRecord.objects.exists()
    assert not Locality.objects.filter(name__iexact="Unauthorized New Street").exists()

    creator = user_with_role("side-effect-owner@example.test", ROLE_OWNER)
    record = create_record_for(creator, "SideEffectUpdate")
    other = user_with_role("side-effect-agent@example.test", ROLE_AGENT)

    with pytest.raises(PermissionDenied):
        update_property_record(
            actor=other,
            property_record=record,
            locality_name="Unauthorized Update Street",
            locality_kind=Locality.Kind.STREET,
        )

    record.refresh_from_db()
    assert record.locality.name == "SideEffectUpdate Street"
    assert not Locality.objects.filter(name__iexact="Unauthorized Update Street").exists()
