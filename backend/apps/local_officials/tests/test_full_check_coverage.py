from datetime import timedelta
import pytest
from django.utils import timezone
from apps.local_officials.full_check import assign_locality, eligible_officials, validate_answers, QUESTIONS
from apps.local_officials.policies import can_review_field_verification
from apps.verification.models import PropertyRelationship
from apps.verification.tests.test_field_lifecycle import submitted_field
from .test_field_verification_authorization import official_with_assignment as old_official_with_assignment
from rest_framework.exceptions import ValidationError

pytestmark = pytest.mark.django_db


def official_with_assignment(property_record):
    from apps.leads.tests.test_leads import grant
    official, manager, profile, assignment = old_official_with_assignment(property_record)
    for user, role in [(official, "local_official"), (manager, "management")]:
        user.account_category = "operational"
        user.save(update_fields=["account_category"])
        grant(user, role)
    return official, manager, profile, assignment


def test_broad_jurisdiction_does_not_grant_full_check_locality_eligibility():
    _, property_record, _, _ = submitted_field()
    official, manager, profile, _ = official_with_assignment(property_record)
    assert eligible_officials(property_record) == []
    assign_locality(actor=manager, official=profile, locality=property_record.locality)
    assert [item.user_id for item in eligible_officials(property_record)] == [official.pk]


def test_property_creator_and_declared_relationship_are_excluded():
    _, property_record, _, field = submitted_field()
    official, manager, profile, _ = official_with_assignment(property_record)
    assign_locality(actor=manager, official=profile, locality=property_record.locality)
    property_record.created_by = official
    property_record.save(update_fields=["created_by"])
    assert not can_review_field_verification(official, field)
    assert eligible_officials(property_record) == []


def test_expired_exact_coverage_and_declared_conflict_fail_closed():
    _, property_record, _, _ = submitted_field()
    official, manager, profile, _ = official_with_assignment(property_record)
    row = assign_locality(actor=manager, official=profile, locality=property_record.locality)
    PropertyRelationship.objects.create(property=property_record, user=official, reason="Declared relative of owner")
    assert eligible_officials(property_record) == []
    row.starts_at = timezone.now() - timedelta(days=2)
    row.expires_at = timezone.now() - timedelta(days=1)
    row.save()
    assert eligible_officials(property_record) == []


def test_questionnaire_preserves_exact_five_questions_and_requires_yes_no():
    answers = {str(n): {"answer": "YES", "comment": "Office records checked"} for n in range(1, 6)}
    result = validate_answers(answers)
    assert tuple(item["question"] for item in result.values()) == QUESTIONS
    for invalid in [{}, {**answers, "6": {"answer": "YES"}}, {**answers, "2": {"answer": "MAYBE"}}]:
        with pytest.raises(ValidationError):
            validate_answers(invalid)
