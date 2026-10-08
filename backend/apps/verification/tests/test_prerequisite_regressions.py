import pytest
from django.db import DatabaseError, connection, transaction
from rest_framework.exceptions import ValidationError
from apps.verification.models import PropertyVerificationEvidence
from apps.verification.services import get_effective_verification_level, approve_field_verification
from .test_document_lifecycle import submit_ready_document
from .test_field_lifecycle import submitted_field, local_official

pytestmark = pytest.mark.django_db


def test_submitted_evidence_resists_raw_database_update_and_delete():
    _, _, verification = submit_ready_document()
    evidence = verification.evidence.get()
    for sql in ["UPDATE verification_propertyverificationevidence SET evidence_ref='replacement' WHERE id=%s", "DELETE FROM verification_propertyverificationevidence WHERE id=%s"]:
        with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(sql, [evidence.pk])


def test_submitted_evidence_rejects_update_delete_and_queryset_mutations():
    _, _, verification = submit_ready_document()
    evidence = verification.evidence.get()
    original = evidence.evidence_ref
    evidence.evidence_ref = "private/replacement"
    for operation in [lambda: evidence.save(), lambda: evidence.delete(), lambda: PropertyVerificationEvidence.objects.filter(pk=evidence.pk).update(evidence_ref="private/replacement"), lambda: PropertyVerificationEvidence.objects.filter(pk=evidence.pk).delete()]:
        with pytest.raises(ValidationError):
            operation()
    evidence.refresh_from_db()
    assert evidence.evidence_ref == original


def test_field_approval_never_grants_ownership_level_three():
    owner, property_record, _, field = submitted_field()
    approve_field_verification(verification=field, reviewer=local_official())
    assert get_effective_verification_level(user=owner, property_record=property_record) == 2


def test_property_creator_cannot_review_someone_elses_field_submission():
    from rest_framework.exceptions import PermissionDenied
    _, property_record, _, field = submitted_field()
    reviewer = local_official()
    property_record.created_by = reviewer
    property_record.save(update_fields=["created_by"])
    with pytest.raises(PermissionDenied):
        approve_field_verification(verification=field, reviewer=reviewer)


def test_evidence_corrections_append_and_keep_previous_reference():
    owner, _, verification = submit_ready_document()
    original = verification.evidence.get()
    correction = PropertyVerificationEvidence.objects.create(
        verification=verification, evidence_type=original.evidence_type,
        evidence_ref="private/corrected-version", created_by=owner, supersedes=original,
    )
    original.refresh_from_db()
    assert original.evidence_ref != correction.evidence_ref
    assert verification.evidence.count() == 2
