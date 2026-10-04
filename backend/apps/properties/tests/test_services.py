from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.gis.geos import Point, Polygon
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.localities.models import District, Locality, Region, Ward
from apps.properties.models import PropertyRecord
from apps.properties import services
from apps.properties.services import (
    create_property_record,
    generate_property_id,
    get_property_record,
    resolve_property_locality,
    update_property_record,
)
from apps.roles.catalog import ROLE_AGENT, ROLE_BUYER, ROLE_MANAGEMENT, ROLE_OWNER
from apps.roles.models import Role, UserRole
from apps.roles.services import bootstrap_canonical_roles


pytestmark = pytest.mark.django_db


def create_user(email, *, is_active=True):
    return get_user_model().objects.create_user(
        email=email,
        phone=f"+255{abs(hash(email)) % 1000000000:09d}",
        full_name="Property Service User",
        password="StrongPass123!",
        is_active=is_active,
    )


def grant_role(user, role_code, *, is_active=True, role_active=True):
    bootstrap_canonical_roles()
    role = Role.objects.get(code=role_code)
    role.is_active = role_active
    role.save(update_fields=["is_active"])
    return UserRole.objects.create(user=user, role=role, is_active=is_active)


def create_hierarchy(prefix="Service", *, approved=True):
    region = Region.objects.create(name=f"{prefix} Region")
    district = District.objects.create(region=region, name=f"{prefix} District")
    ward = Ward.objects.create(district=district, name=f"{prefix} Ward")
    locality = Locality.objects.create(
        ward=ward,
        name=f"{prefix} Street",
        kind=Locality.Kind.STREET,
        approved=approved,
    )
    return region, district, ward, locality


def valid_attrs(prefix="Service", **overrides):
    region, district, ward, locality = create_hierarchy(prefix)
    attrs = {
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
    attrs.update(overrides)
    return attrs


def typed_attrs(prefix="Typed", *, name="Typed Locality", kind=Locality.Kind.STREET, **overrides):
    attrs = valid_attrs(prefix=prefix)
    attrs.pop("locality")
    attrs["locality_name"] = name
    attrs["locality_kind"] = kind
    attrs.update(overrides)
    return attrs


def lister(role_code=ROLE_OWNER, email="owner@example.test"):
    user = create_user(email)
    grant_role(user, role_code)
    return user


def manager(email="manager@example.test"):
    user = create_user(email)
    grant_role(user, ROLE_MANAGEMENT)
    return user


def create_record(actor=None, **overrides):
    return create_property_record(actor=actor or lister(), **valid_attrs(**overrides))


def test_property_id_format_length_and_no_business_data(monkeypatch):
    actor = lister(email="format@example.test")
    attrs = valid_attrs(prefix="Format", category=PropertyRecord.Category.COMMERCIAL)
    monkeypatch.setattr(services, "_property_id_token", lambda: "ABCDEF1234567890")

    record = create_property_record(actor=actor, **attrs)

    assert record.property_id == "OWR-ABCDEF1234567890"
    assert len(record.property_id) <= 50
    assert actor.email not in record.property_id
    assert actor.phone not in record.property_id
    assert attrs["locality"].name not in record.property_id
    assert attrs["category"] not in record.property_id


def test_generate_property_id_retries_on_existing_candidate(monkeypatch):
    actor = lister(email="retry@example.test")
    existing = create_property_record(actor=actor, **valid_attrs(prefix="RetryExisting"))

    tokens = iter([existing.property_id.removeprefix("OWR-"), "NEW0000000000001"])
    monkeypatch.setattr(services, "_property_id_token", lambda: next(tokens))

    generated = generate_property_id()

    assert generated == "OWR-NEW0000000000001"


def test_exhausted_property_id_generation_raises(monkeypatch):
    actor = lister(email="exhaust@example.test")
    token = "COLLISION000000"
    create_property_record(actor=actor, **valid_attrs(prefix="Exhaust"))
    PropertyRecord.objects.filter(created_by=actor).update(property_id=f"OWR-{token}")
    monkeypatch.setattr(services, "_property_id_token", lambda: token)

    with pytest.raises(ValidationError):
        generate_property_id()


@pytest.mark.parametrize("role_code", [ROLE_OWNER, ROLE_AGENT])
def test_owner_or_agent_can_create(role_code):
    actor = lister(role_code, email=f"{role_code}@example.test")

    record = create_property_record(actor=actor, **valid_attrs(prefix=role_code))

    assert record.created_by == actor
    assert record.property_id.startswith("OWR-")


def test_user_with_owner_and_agent_can_create():
    actor = lister(ROLE_OWNER, email="both@example.test")
    grant_role(actor, ROLE_AGENT)

    record = create_property_record(actor=actor, **valid_attrs(prefix="Both"))

    assert record.created_by == actor


@pytest.mark.parametrize("role_code", [ROLE_BUYER, ROLE_MANAGEMENT])
def test_buyer_or_management_only_cannot_create(role_code):
    actor = create_user(f"{role_code}@example.test")
    grant_role(actor, role_code)

    with pytest.raises(PermissionDenied):
        create_property_record(actor=actor, **valid_attrs(prefix=role_code))


def test_unauthenticated_unsaved_inactive_and_inactive_assignment_create_denied():
    with pytest.raises(PermissionDenied):
        create_property_record(actor=AnonymousUser(), **valid_attrs(prefix="Anonymous"))

    unsaved = get_user_model()(email="unsaved@example.test")
    with pytest.raises(PermissionDenied):
        create_property_record(actor=unsaved, **valid_attrs(prefix="Unsaved"))

    inactive = create_user("inactive@example.test", is_active=False)
    grant_role(inactive, ROLE_OWNER)
    with pytest.raises(PermissionDenied):
        create_property_record(actor=inactive, **valid_attrs(prefix="Inactive"))

    inactive_assignment = create_user("inactive-assignment@example.test")
    grant_role(inactive_assignment, ROLE_OWNER, is_active=False)
    with pytest.raises(PermissionDenied):
        create_property_record(actor=inactive_assignment, **valid_attrs(prefix="InactiveAssignment"))


def test_create_server_controls_property_id_and_created_by():
    actor = lister(email="server-control@example.test")
    other = create_user("other-control@example.test")

    with pytest.raises(ValidationError):
        create_property_record(
            actor=actor,
            **valid_attrs(prefix="ServerControl"),
            property_id="CLIENT-CHOSEN",
            created_by=other,
        )

    assert not PropertyRecord.objects.filter(property_id="CLIENT-CHOSEN").exists()


def test_create_persists_valid_gis_and_locality_data():
    boundary = Polygon(((39.20, -6.79), (39.21, -6.79), (39.21, -6.80), (39.20, -6.80), (39.20, -6.79)), srid=4326)
    record = create_record(prefix="GIS", boundary=boundary)

    assert record.pin.srid == 4326
    assert record.boundary.srid == 4326
    assert record.locality.ward == record.ward
    assert record.ward.district == record.district
    assert record.district.region == record.region


def test_create_rejects_invalid_hierarchy_and_non_positive_size():
    actor = lister(email="invalid-create@example.test")
    region, district, ward, _ = create_hierarchy("ValidCreate")
    _, _, _, other_locality = create_hierarchy("InvalidCreate")

    with pytest.raises(ValidationError):
        create_record(
            actor=actor,
            prefix="BadHierarchy",
            region=region,
            district=district,
            ward=ward,
            locality=other_locality,
        )

    with pytest.raises(ValidationError):
        create_record(actor=actor, prefix="BadSize", stated_size=Decimal("0"))


def test_creator_can_get_and_unknown_property_id_is_safe():
    actor = lister(email="get-creator@example.test")
    record = create_record(actor=actor, prefix="GetCreator")

    assert get_property_record(actor=actor, property_id=record.property_id) == record

    with pytest.raises(NotFound):
        get_property_record(actor=actor, property_id="OWR-DOESNOTEXIST")


def test_unrelated_lister_denied_and_management_can_get():
    creator = lister(email="get-owner@example.test")
    unrelated = lister(ROLE_AGENT, email="get-agent@example.test")
    record = create_record(actor=creator, prefix="GetAccess")

    with pytest.raises(PermissionDenied):
        get_property_record(actor=unrelated, property_id=record.property_id)

    assert get_property_record(actor=manager(), property_id=record.property_id) == record


def test_inactive_actor_cannot_get():
    creator = lister(email="get-inactive-creator@example.test")
    record = create_record(actor=creator, prefix="GetInactive")
    creator.is_active = False
    creator.save(update_fields=["is_active"])

    with pytest.raises(PermissionDenied):
        get_property_record(actor=creator, property_id=record.property_id)


def test_creator_and_management_can_update():
    creator = lister(email="update-creator@example.test")
    record = create_record(actor=creator, prefix="UpdateCreator")

    updated = update_property_record(actor=creator, property_record=record, category=PropertyRecord.Category.HOUSE)
    assert updated.category == PropertyRecord.Category.HOUSE

    updated = update_property_record(actor=manager(), property_record=record, title_type=PropertyRecord.TitleType.CCRO)
    assert updated.title_type == PropertyRecord.TitleType.CCRO


def test_unrelated_lister_cannot_update_and_persisted_state_is_unchanged():
    creator = lister(email="update-owner@example.test")
    unrelated = lister(ROLE_AGENT, email="update-agent@example.test")
    record = create_record(actor=creator, prefix="UpdateDenied")
    original_category = record.category

    with pytest.raises(PermissionDenied):
        update_property_record(actor=unrelated, property_record=record, category=PropertyRecord.Category.COMMERCIAL)

    record.refresh_from_db()
    assert record.category == original_category


def test_update_rejects_immutable_fields():
    creator = lister(email="immutable@example.test")
    other = create_user("immutable-other@example.test")
    record = create_record(actor=creator, prefix="Immutable")

    with pytest.raises(ValidationError):
        update_property_record(
            actor=creator,
            property_record=record,
            property_id="CLIENT-CHANGE",
            created_by=other,
        )

    record.refresh_from_db()
    assert record.created_by == creator
    assert record.property_id != "CLIENT-CHANGE"


def test_partial_update_resulting_in_invalid_hierarchy_is_rejected_without_persisting():
    creator = lister(email="hierarchy-update@example.test")
    record = create_record(actor=creator, prefix="HierarchyUpdate")
    _, _, _, other_locality = create_hierarchy("OtherHierarchyUpdate")
    original_locality_id = record.locality_id

    with pytest.raises(ValidationError):
        update_property_record(actor=creator, property_record=record, locality=other_locality)

    record.refresh_from_db()
    assert record.locality_id == original_locality_id


def test_valid_hierarchy_update_succeeds():
    creator = lister(email="valid-hierarchy-update@example.test")
    record = create_record(actor=creator, prefix="ValidHierarchyOriginal")
    region, district, ward, locality = create_hierarchy("ValidHierarchyNew")

    updated = update_property_record(
        actor=creator,
        property_record=record,
        region=region,
        district=district,
        ward=ward,
        locality=locality,
    )

    assert updated.locality == locality
    assert updated.ward == ward
    assert updated.district == district
    assert updated.region == region


@pytest.mark.parametrize(
    "field,value",
    [
        ("category", "APARTMENT"),
        ("title_type", "TITLE_DEED"),
        ("stated_size", Decimal("-1")),
    ],
)
def test_update_preserves_model_validation(field, value):
    creator = lister(email=f"validation-{field}@example.test")
    record = create_record(actor=creator, prefix=f"Validation{field}")

    with pytest.raises(ValidationError):
        update_property_record(actor=creator, property_record=record, **{field: value})


def test_no_delete_service_listing_model_lister_gate_audit_or_legacy_imports():
    assert not hasattr(services, "delete_property_record")
    assert not hasattr(services, "archive_property_record")
    assert "Listing" not in {model.__name__ for model in services.PropertyRecord._meta.apps.get_models()}

    imports = getattr(services, "__dict__", {})
    assert "legacy_authorization_services" not in imports
    assert "ListerIdentity" not in imports


def test_existing_approved_or_pending_locality_can_be_used_without_duplication_or_status_change():
    actor = lister(email="existing-locality@example.test")
    approved_attrs = valid_attrs(prefix="ExistingApproved")
    approved = approved_attrs["locality"]
    pending_attrs = valid_attrs(prefix="ExistingPending")
    pending_attrs["locality"].approved = False
    pending_attrs["locality"].save(update_fields=["approved"])
    pending = pending_attrs["locality"]

    approved_record = create_property_record(actor=actor, **approved_attrs)
    pending_record = create_property_record(actor=actor, **pending_attrs)

    assert approved_record.locality == approved
    assert pending_record.locality == pending
    approved.refresh_from_db()
    pending.refresh_from_db()
    assert approved.approved is True
    assert pending.approved is False
    assert Locality.objects.filter(ward=approved.ward, kind=approved.kind, name__iexact=approved.name).count() == 1
    assert Locality.objects.filter(ward=pending.ward, kind=pending.kind, name__iexact=pending.name).count() == 1


def test_existing_locality_path_rejects_invalid_hierarchy_parts():
    actor = lister(email="invalid-existing-locality@example.test")
    region, district, ward, locality = create_hierarchy("ExistingValid")
    other_region, other_district, other_ward, other_locality = create_hierarchy("ExistingOther")

    with pytest.raises(ValidationError):
        create_property_record(actor=actor, **valid_attrs(prefix="BadLocality", region=region, district=district, ward=ward, locality=other_locality))
    with pytest.raises(ValidationError):
        create_property_record(actor=actor, **valid_attrs(prefix="BadWard", region=region, district=district, ward=other_ward, locality=locality))
    with pytest.raises(ValidationError):
        create_property_record(actor=actor, **valid_attrs(prefix="BadDistrict", region=region, district=other_district, ward=ward, locality=locality))
    with pytest.raises(ValidationError):
        create_property_record(actor=actor, **valid_attrs(prefix="BadRegion", region=other_region, district=district, ward=ward, locality=locality))


@pytest.mark.parametrize("kind", [Locality.Kind.STREET, Locality.Kind.VILLAGE])
def test_typed_locality_creates_pending_locality_and_property_references_it(kind):
    actor = lister(email=f"typed-{kind}@example.test")

    record = create_property_record(
        actor=actor,
        **typed_attrs(prefix=f"Typed{kind}", name="  New Typed Locality  ", kind=kind),
    )

    assert record.locality.name == "New Typed Locality"
    assert record.locality.kind == kind
    assert record.locality.approved is False
    assert record.locality.created_by == actor
    assert record.locality.ward == record.ward


@pytest.mark.parametrize(
    "name,kind",
    [
        ("", Locality.Kind.STREET),
        ("   ", Locality.Kind.STREET),
        ("Valid Name", "area"),
    ],
)
def test_typed_locality_invalid_name_or_kind_rejected(name, kind):
    actor = lister(email=f"typed-invalid-{abs(hash((name, kind))) % 10000}@example.test")

    with pytest.raises(ValidationError):
        create_property_record(actor=actor, **typed_attrs(prefix=f"TypedInvalid{abs(hash(name))}", name=name, kind=kind))


def test_typed_locality_reuses_case_insensitive_pending_match():
    actor = lister(email="typed-pending-reuse@example.test")
    attrs = typed_attrs(prefix="TypedPendingReuse", name="Kimara", kind=Locality.Kind.STREET)
    first = create_property_record(actor=actor, **attrs)
    second = create_property_record(
        actor=actor,
        **typed_attrs(
            prefix="TypedPendingReuseSecond",
            name="kIMAra",
            kind=Locality.Kind.STREET,
            region=first.region,
            district=first.district,
            ward=first.ward,
        ),
    )

    assert second.locality == first.locality
    assert Locality.objects.filter(ward=first.ward, kind=Locality.Kind.STREET, name__iexact="kimara").count() == 1


def test_typed_locality_reuses_approved_match_without_downgrading():
    actor = lister(email="typed-approved-reuse@example.test")
    attrs = valid_attrs(prefix="TypedApprovedReuse")
    approved = attrs["locality"]
    typed = {
        key: attrs[key]
        for key in ("category", "pin", "boundary", "region", "district", "ward", "stated_size", "size_unit", "title_type")
    }
    typed["locality_name"] = approved.name.lower()
    typed["locality_kind"] = approved.kind

    record = create_property_record(actor=actor, **typed)

    assert record.locality == approved
    approved.refresh_from_db()
    assert approved.approved is True
    assert Locality.objects.filter(ward=approved.ward, kind=approved.kind, name__iexact=approved.name).count() == 1


def test_same_typed_name_in_different_wards_and_different_kinds_remain_distinct():
    actor = lister(email="typed-distinct@example.test")
    street = create_property_record(actor=actor, **typed_attrs(prefix="DistinctStreet", name="Shared Name", kind=Locality.Kind.STREET))
    village = create_property_record(
        actor=actor,
        **typed_attrs(
            prefix="DistinctVillage",
            name="Shared Name",
            kind=Locality.Kind.VILLAGE,
            region=street.region,
            district=street.district,
            ward=street.ward,
        ),
    )
    other_ward = create_property_record(actor=actor, **typed_attrs(prefix="DistinctOtherWard", name="Shared Name", kind=Locality.Kind.STREET))

    assert street.locality != village.locality
    assert street.locality != other_ward.locality


@pytest.mark.parametrize(
    "override",
    [
        {"locality_name": "Extra", "locality_kind": Locality.Kind.STREET},
        {"locality": None, "locality_name": "Name Only"},
        {"locality": None, "locality_kind": Locality.Kind.STREET},
        {"locality": None},
    ],
)
def test_ambiguous_or_missing_locality_input_fails_without_creating_property(override):
    actor = lister(email=f"ambiguous-{abs(hash(tuple(sorted(override)))) % 10000}@example.test")
    attrs = valid_attrs(prefix=f"Ambiguous{abs(hash(tuple(sorted(override))))}")
    attrs.update(override)
    before = PropertyRecord.objects.count()

    with pytest.raises(ValidationError):
        create_property_record(actor=actor, **attrs)

    assert PropertyRecord.objects.count() == before


def test_create_typed_locality_rolls_back_when_property_validation_fails():
    actor = lister(email="create-rollback@example.test")
    attrs = typed_attrs(prefix="CreateRollback", name="Rollback Locality", kind=Locality.Kind.STREET)
    attrs["stated_size"] = Decimal("0")

    with pytest.raises(ValidationError):
        create_property_record(actor=actor, **attrs)

    assert not PropertyRecord.objects.exists()
    assert not Locality.objects.filter(ward=attrs["ward"], name__iexact="Rollback Locality").exists()


def test_update_can_move_to_existing_or_typed_locality_and_management_can_update():
    creator = lister(email="update-locality@example.test")
    record = create_record(actor=creator, prefix="UpdateLocalityOriginal")
    region, district, ward, locality = create_hierarchy("UpdateLocalityExisting")

    updated = update_property_record(
        actor=creator,
        property_record=record,
        region=region,
        district=district,
        ward=ward,
        locality=locality,
    )
    assert updated.locality == locality

    manager_actor = manager(email="update-locality-manager@example.test")
    updated = update_property_record(
        actor=manager_actor,
        property_record=record,
        locality_name="Manager Typed",
        locality_kind=Locality.Kind.VILLAGE,
    )
    assert updated.locality.name == "Manager Typed"
    assert updated.locality.approved is False
    assert updated.locality.created_by == manager_actor


def test_unrelated_lister_still_cannot_update_with_typed_locality():
    creator = lister(email="typed-update-owner@example.test")
    unrelated = lister(ROLE_AGENT, email="typed-update-agent@example.test")
    record = create_record(actor=creator, prefix="TypedUpdateDenied")

    with pytest.raises(PermissionDenied):
        update_property_record(
            actor=unrelated,
            property_record=record,
            locality_name="Denied Locality",
            locality_kind=Locality.Kind.STREET,
        )

    assert not Locality.objects.filter(name__iexact="Denied Locality").exists()


def test_update_ward_change_without_compatible_locality_fails_and_valid_change_succeeds():
    creator = lister(email="ward-change@example.test")
    record = create_record(actor=creator, prefix="WardChangeOriginal")
    region, district, ward, locality = create_hierarchy("WardChangeNew")

    with pytest.raises(ValidationError):
        update_property_record(actor=creator, property_record=record, region=region, district=district, ward=ward)

    updated = update_property_record(
        actor=creator,
        property_record=record,
        region=region,
        district=district,
        ward=ward,
        locality=locality,
    )
    assert updated.locality == locality


def test_update_typed_locality_rolls_back_when_later_validation_fails():
    creator = lister(email="update-rollback@example.test")
    record = create_record(actor=creator, prefix="UpdateRollback")
    original_locality_id = record.locality_id
    original_size = record.stated_size

    with pytest.raises(ValidationError):
        update_property_record(
            actor=creator,
            property_record=record,
            locality_name="Update Rollback Locality",
            locality_kind=Locality.Kind.STREET,
            stated_size=Decimal("0"),
        )

    record.refresh_from_db()
    assert record.locality_id == original_locality_id
    assert record.stated_size == original_size
    assert not Locality.objects.filter(ward=record.ward, name__iexact="Update Rollback Locality").exists()


def test_resolver_reuses_m04_pending_service(monkeypatch):
    actor = lister(email="resolver-m04@example.test")
    attrs = valid_attrs(prefix="ResolverM04")
    attrs.pop("locality")
    calls = {}

    def fake_create_pending_locality(**kwargs):
        calls.update(kwargs)
        return Locality.objects.create(
            ward=kwargs["ward"],
            name=kwargs["name"].strip(),
            kind=kwargs["kind"],
            approved=False,
            created_by=kwargs["actor"],
        )

    monkeypatch.setattr(services, "create_pending_locality", fake_create_pending_locality)
    locality = resolve_property_locality(
        actor=actor,
        region=attrs["region"],
        district=attrs["district"],
        ward=attrs["ward"],
        locality_name="Resolver Pending",
        locality_kind=Locality.Kind.STREET,
    )

    assert locality.name == "Resolver Pending"
    assert calls["actor"] == actor
    assert calls["ward"] == attrs["ward"]
    assert calls["kind"] == Locality.Kind.STREET
