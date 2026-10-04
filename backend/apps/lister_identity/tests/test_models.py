import uuid

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from apps.lister_identity.models import ListerIdentity
from apps.roles.catalog import CANONICAL_ROLE_CODES
from apps.roles.models import Role
from apps.roles.services import bootstrap_canonical_roles


pytestmark = pytest.mark.django_db


def create_user(email):
    return get_user_model().objects.create_user(
        email=email,
        phone=f"+255{abs(hash(email)) % 1000000000:09d}",
        full_name="Synthetic Lister",
        password="StrongPass123!",
    )


def create_identity(user=None, **overrides):
    data = {
        "user": user or create_user("lister@example.test"),
        "national_id_number": "001234567890",
    }
    data.update(overrides)
    return ListerIdentity.objects.create(**data)


def test_lister_identity_app_loads_and_app_labels_are_unique():
    labels = [config.label for config in apps.get_app_configs()]

    assert apps.get_app_config("lister_identity").name == "apps.lister_identity"
    assert len(labels) == len(set(labels))


def test_lister_identity_creation_uuid_timestamps_and_default_status():
    identity = create_identity()

    assert isinstance(identity.pk, uuid.UUID)
    assert identity.created_at is not None
    assert identity.updated_at is not None
    assert identity.status == ListerIdentity.Status.PENDING


@pytest.mark.parametrize(
    "status",
    [
        ListerIdentity.Status.PENDING,
        ListerIdentity.Status.APPROVED,
        ListerIdentity.Status.REJECTED,
        ListerIdentity.Status.EXPIRED,
    ],
)
def test_documented_status_choices_are_accepted(status):
    identity = ListerIdentity(user=create_user(f"{status.lower()}@example.test"), national_id_number="001", status=status)

    identity.full_clean()


def test_undocumented_status_rejected_through_validation():
    identity = ListerIdentity(
        user=create_user("bad-status@example.test"),
        national_id_number="001",
        status="UNDER_REVIEW",
    )

    with pytest.raises(ValidationError):
        identity.full_clean()


def test_identity_belongs_to_user_and_reverse_relationship_works():
    user = create_user("reverse@example.test")
    identity = create_identity(user=user)

    assert identity.user == user
    assert user.lister_identity == identity


def test_one_identity_per_user_enforced():
    user = create_user("one-identity@example.test")
    create_identity(user=user)

    with pytest.raises(IntegrityError), transaction.atomic():
        create_identity(user=user, national_id_number="009999999999")


def test_different_users_can_each_have_identity():
    first = create_identity(user=create_user("first@example.test"))
    second = create_identity(user=create_user("second@example.test"), national_id_number="001234567890")

    assert first.user != second.user
    assert ListerIdentity.objects.count() == 2


def test_national_id_is_string_preserves_leading_zeroes_and_is_not_unique():
    first = create_identity(user=create_user("first-id@example.test"), national_id_number="001234")
    second = create_identity(user=create_user("second-id@example.test"), national_id_number="001234")

    assert first.national_id_number == "001234"
    assert second.national_id_number == "001234"
    assert isinstance(first.national_id_number, str)


def test_sensitive_values_are_not_leaked_through_string_representation():
    identity = create_identity(
        national_id_number="001234SECRET",
        national_id_photo_ref="private/id-photo-key",
        live_selfie_ref="private/selfie-key",
    )
    rendered = str(identity)

    assert "001234SECRET" not in rendered
    assert "private/id-photo-key" not in rendered
    assert "private/selfie-key" not in rendered


def test_media_references_can_be_stored_as_private_opaque_references():
    identity = create_identity(
        national_id_photo_ref="private/lister-id-photo/object-key",
        live_selfie_ref="private/lister-selfie/object-key",
    )

    assert identity.national_id_photo_ref == "private/lister-id-photo/object-key"
    assert identity.live_selfie_ref == "private/lister-selfie/object-key"


def test_workflow_fields_are_nullable_or_blank_as_designed():
    identity = create_identity()

    assert identity.submitted_at is None
    assert identity.reviewed_at is None
    assert identity.reviewed_by is None
    assert identity.review_reason == ""
    assert identity.expires_at is None


def test_reviewer_relation_works_and_is_protected_from_deletion():
    reviewer = create_user("reviewer@example.test")
    identity = create_identity(
        reviewed_by=reviewer,
        reviewed_at=timezone.now(),
        review_reason="Looks valid.",
    )

    assert identity.reviewed_by == reviewer
    with pytest.raises(ProtectedError):
        reviewer.delete()


def test_self_review_validation_fails():
    user = create_user("self-review@example.test")
    identity = ListerIdentity(user=user, reviewed_by=user, national_id_number="001")

    with pytest.raises(ValidationError):
        identity.full_clean()


def test_architecture_boundaries_for_m05b():
    bootstrap_canonical_roles()

    assert set(Role.objects.filter(code__in=CANONICAL_ROLE_CODES).values_list("code", flat=True)) == set(
        CANONICAL_ROLE_CODES
    )
    assert "lister" not in CANONICAL_ROLE_CODES

    model_names = {model.__name__ for model in apps.get_models()}
    assert "Property" not in model_names

    identity_fields = {field.name for field in ListerIdentity._meta.get_fields()}
    assert {"email", "password", "phone", "full_name", "preferred_language", "is_email_verified"}.isdisjoint(
        identity_fields
    )
    assert {"region", "district", "ward", "locality", "areas_covered", "property_types"}.isdisjoint(identity_fields)
    assert {"listing", "listings", "lister_kind", "selling_price", "owner_price"}.isdisjoint(identity_fields)
