import pytest
from django.contrib.gis.geos import Point, Polygon
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.localities.models import District, Locality, Region, Ward
from apps.properties import services as property_services
from apps.properties.models import PropertyRecord
from apps.properties.services import update_property_record
from apps.verification.audit_events import VERIFICATION_PROPERTY_CHANGE_INVALIDATED
from apps.verification.models import PropertyVerification
from apps.verification.services import (
    approve_document_verification,
    approve_field_verification,
    get_effective_verification_level,
    submit_document_verification,
)

from .test_document_lifecycle import document_evidence, verifier
from .test_field_lifecycle import field_evidence, local_official, submitted_field
from .test_document_lifecycle import create_property, owner_with_level_one


pytestmark = pytest.mark.django_db


def test_material_field_set_matches_verified_property_facts():
    from apps.verification.services import PROPERTY_VERIFICATION_MATERIAL_FIELDS

    assert PROPERTY_VERIFICATION_MATERIAL_FIELDS == {
        "category",
        "pin",
        "boundary",
        "region",
        "district",
        "ward",
        "locality",
        "stated_size",
        "size_unit",
        "title_type",
    }


def replacement_hierarchy(prefix):
    region = Region.objects.create(name=f"{prefix} Region")
    district = District.objects.create(region=region, name=f"{prefix} District")
    ward = Ward.objects.create(district=district, name=f"{prefix} Ward")
    locality = Locality.objects.create(ward=ward, name=f"{prefix} Street", kind=Locality.Kind.STREET, approved=True)
    return region, district, ward, locality


@pytest.mark.parametrize(
    "field",
    ["category", "pin", "boundary", "stated_size", "size_unit", "title_type", "hierarchy"],
)
def test_every_material_property_change_revokes_pending_verification(field):
    owner = owner_with_level_one()
    property_record = create_property(owner)
    pending = submit_document_verification(
        property_record=property_record,
        submitted_by=owner,
        evidence=document_evidence(f"private/{field}-document"),
    )

    updates = {
        "category": {"category": PropertyRecord.Category.HOUSE},
        "pin": {"pin": Point(39.3083, -6.6924, srid=4326)},
        "boundary": {
            "boundary": Polygon(
                ((39.20, -6.79), (39.21, -6.79), (39.21, -6.80), (39.20, -6.79)),
                srid=4326,
            )
        },
        "stated_size": {"stated_size": property_record.stated_size + 1},
        "size_unit": {"size_unit": "acre"},
        "title_type": {"title_type": PropertyRecord.TitleType.REGISTERED_TITLE},
    }
    if field == "hierarchy":
        region, district, ward, locality = replacement_hierarchy("Replacement")
        updates[field] = {"region": region, "district": district, "ward": ward, "locality": locality}

    update_property_record(actor=owner, property_record=property_record, **updates[field])

    pending.refresh_from_db()
    assert pending.status == PropertyVerification.Status.REVOKED
    audit = AuditLog.objects.get(action=VERIFICATION_PROPERTY_CHANGE_INVALIDATED, entity_id=str(pending.pk))
    expected_fields = {field} if field != "hierarchy" else {"region", "district", "ward", "locality"}
    assert set(audit.after["changed_fields"]) == expected_fields


def test_same_value_and_metadata_only_updates_do_not_invalidate_verification():
    owner, property_record, _, pending_field = submitted_field()
    field = approve_field_verification(verification=pending_field, reviewer=local_official())
    document = property_record.verifications.get(kind=PropertyVerification.Kind.DOCUMENT)

    update_property_record(actor=owner, property_record=property_record, category=property_record.category)
    document.refresh_from_db()
    field.refresh_from_db()
    assert document.status == PropertyVerification.Status.APPROVED
    assert field.status == PropertyVerification.Status.APPROVED

    property_record.updated_at = timezone.now()
    property_record.save(update_fields=["updated_at"])
    document.refresh_from_db()
    field.refresh_from_db()
    assert document.status == PropertyVerification.Status.APPROVED
    assert field.status == PropertyVerification.Status.APPROVED


def test_material_change_revokes_approved_document_and_preserves_evidence_history():
    owner = owner_with_level_one()
    property_record = create_property(owner)
    document = submit_document_verification(
        property_record=property_record,
        submitted_by=owner,
        evidence=document_evidence(),
    )
    document = approve_document_verification(verification=document, reviewer=verifier())
    evidence_id = document.evidence.get().pk

    update_property_record(actor=owner, property_record=property_record, category=PropertyRecord.Category.HOUSE)

    document.refresh_from_db()
    assert document.status == PropertyVerification.Status.REVOKED
    assert document.revoked_at is not None
    assert document.evidence.filter(pk=evidence_id).exists()
    assert get_effective_verification_level(user=owner, property_record=property_record) == 1

    fresh = submit_document_verification(
        property_record=property_record,
        submitted_by=owner,
        evidence=document_evidence("private/fresh-document"),
    )
    assert fresh.status == PropertyVerification.Status.PENDING


def test_material_change_revokes_approved_document_and_field_and_collapses_to_level_one():
    owner, property_record, document, pending_field = submitted_field()
    field = approve_field_verification(verification=pending_field, reviewer=local_official())
    assert get_effective_verification_level(user=owner, property_record=property_record) == 2

    update_property_record(actor=owner, property_record=property_record, title_type=PropertyRecord.TitleType.SALE_AGREEMENT)

    document.refresh_from_db()
    field.refresh_from_db()
    assert document.status == PropertyVerification.Status.REVOKED
    assert field.status == PropertyVerification.Status.REVOKED
    assert get_effective_verification_level(user=owner, property_record=property_record) == 1


def test_pending_document_is_revoked_and_cannot_be_approved_after_material_change():
    owner = owner_with_level_one()
    property_record = create_property(owner)
    pending = submit_document_verification(
        property_record=property_record,
        submitted_by=owner,
        evidence=document_evidence(),
    )

    update_property_record(actor=owner, property_record=property_record, stated_size=property_record.stated_size + 1)

    pending.refresh_from_db()
    assert pending.status == PropertyVerification.Status.REVOKED
    with pytest.raises(ValidationError):
        approve_document_verification(verification=pending, reviewer=verifier())


def test_property_update_and_invalidation_are_atomic(monkeypatch):
    owner = owner_with_level_one()
    property_record = create_property(owner)
    original_category = property_record.category

    def fail_invalidation(**kwargs):
        raise RuntimeError("verification invalidation failed")

    monkeypatch.setattr(property_services, "invalidate_property_verifications_for_material_change", fail_invalidation)
    with pytest.raises(RuntimeError):
        update_property_record(actor=owner, property_record=property_record, category=PropertyRecord.Category.HOUSE)

    property_record.refresh_from_db()
    assert property_record.category == original_category


def test_invalidation_audit_contains_only_safe_changed_field_names():
    owner = owner_with_level_one()
    property_record = create_property(owner)
    document = approve_document_verification(
        verification=submit_document_verification(
            property_record=property_record,
            submitted_by=owner,
            evidence=document_evidence("private/audit-document"),
        ),
        reviewer=verifier(),
    )

    update_property_record(actor=owner, property_record=property_record, category=PropertyRecord.Category.HOUSE)

    audit = AuditLog.objects.get(action=VERIFICATION_PROPERTY_CHANGE_INVALIDATED, entity_id=str(document.pk))
    assert audit.before["status"] == PropertyVerification.Status.APPROVED
    assert audit.after["status"] == PropertyVerification.Status.REVOKED
    assert audit.after["changed_fields"] == ["category"]
    rendered = repr(audit.before) + repr(audit.after)
    for private_value in ("private/audit-document", "39.2083", "-6.7924"):
        assert private_value not in rendered


def test_duplicate_detection_still_runs_after_material_pin_or_size_update(monkeypatch):
    owner = owner_with_level_one()
    property_record = create_property(owner)
    calls = []
    monkeypatch.setattr(property_services, "_run_duplicate_detection", lambda record, request=None: calls.append(record.pk))

    update_property_record(actor=owner, property_record=property_record, stated_size=property_record.stated_size + 1)

    assert calls == [property_record.pk]
