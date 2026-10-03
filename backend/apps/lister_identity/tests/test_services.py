import uuid

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.lister_identity.evidence import normalize_evidence_reference
from apps.lister_identity.models import ListerIdentity
from apps.lister_identity.services import (
    approve_lister_identity,
    create_lister_identity,
    get_lister_identity,
    reject_lister_identity,
    submit_lister_identity,
    update_lister_identity,
)
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
from apps.roles.services import bootstrap_canonical_roles, user_has_role


pytestmark = pytest.mark.django_db


def create_user(email=None):
    suffix = uuid.uuid4().hex[:10]
    return get_user_model().objects.create_user(
        email=email or f"user-{suffix}@example.test",
        phone=f"+255{uuid.uuid4().int % 1000000000:09d}",
        full_name="Synthetic Lister",
        password="StrongPass123!",
    )


def grant_role(user, role_code, *, active=True):
    bootstrap_canonical_roles()
    role = Role.objects.get(code=role_code)
    return UserRole.objects.create(user=user, role=role, assigned_by=user, is_active=active)


def lister_user(role_code=ROLE_OWNER):
    user = create_user()
    grant_role(user, role_code)
    return user


def management_user():
    user = create_user()
    grant_role(user, ROLE_MANAGEMENT)
    return user


def create_complete_identity(user):
    return create_lister_identity(
        user=user,
        national_id_number=" 001234567890 ",
        national_id_photo_ref=" private/id-photo ",
        live_selfie_ref=" private/selfie ",
    )


def create_submitted_identity(user):
    identity = create_complete_identity(user)
    return submit_lister_identity(user=user, identity=identity)


INVALID_EVIDENCE_REFS = [
    "",
    "   ",
    "http://example.test/id.jpg",
    "https://example.test/id.jpg",
    "data:image/png;base64,SECRET_IMAGE_PAYLOAD",
    "iVBORw0KGgo" + "A" * 140,
    "../private/id-photo",
    "..\\private\\id-photo",
    "x" * 501,
    12345,
]


@pytest.mark.parametrize("role_code", [ROLE_OWNER, ROLE_AGENT])
def test_service_create_allowed_for_owner_and_agent(role_code):
    user = lister_user(role_code)

    identity = create_lister_identity(user=user, national_id_number=" 001234 ")

    assert identity.user == user
    assert identity.national_id_number == "001234"
    assert identity.status == ListerIdentity.Status.PENDING
    assert identity.submitted_at is None


def test_service_create_owner_and_agent_still_limited_to_one_identity():
    user = create_user()
    grant_role(user, ROLE_OWNER)
    grant_role(user, ROLE_AGENT)

    create_lister_identity(user=user, national_id_number="001")
    with pytest.raises(ValidationError):
        create_lister_identity(user=user, national_id_number="002")

    assert ListerIdentity.objects.filter(user=user).count() == 1


def test_service_create_denies_buyer_only_unauthenticated_and_unpersisted_users():
    buyer = create_user()
    grant_role(buyer, ROLE_BUYER)
    unsaved = get_user_model()(email="unsaved@example.test")

    for actor in (buyer, AnonymousUser(), unsaved):
        with pytest.raises(PermissionDenied):
            create_lister_identity(user=actor, national_id_number="001")


def test_service_create_denies_inactive_lister_assignment_and_inactive_role():
    inactive_assignment_user = create_user()
    grant_role(inactive_assignment_user, ROLE_OWNER, active=False)
    with pytest.raises(PermissionDenied):
        create_lister_identity(user=inactive_assignment_user, national_id_number="001")

    inactive_role_user = create_user()
    grant_role(inactive_role_user, ROLE_OWNER)
    Role.objects.filter(code=ROLE_OWNER).update(is_active=False)
    with pytest.raises(PermissionDenied):
        create_lister_identity(user=inactive_role_user, national_id_number="001")


def test_service_create_initializes_workflow_without_auto_submission():
    identity = create_lister_identity(user=lister_user(), national_id_number="")

    assert identity.status == ListerIdentity.Status.PENDING
    assert identity.submitted_at is None
    assert identity.reviewed_at is None
    assert identity.reviewed_by is None
    assert identity.review_reason == ""
    assert identity.expires_at is None


def test_service_get_requires_existing_own_identity():
    user = lister_user()

    with pytest.raises(NotFound):
        get_lister_identity(user=user)

    identity = create_lister_identity(user=user, national_id_number="001")
    assert get_lister_identity(user=user) == identity


def test_service_update_allowed_fields_pre_submit_and_trims_strings():
    user = lister_user()
    identity = create_lister_identity(user=user, national_id_number="001")

    updated = update_lister_identity(
        user=user,
        national_id_number=" 009 ",
        national_id_photo_ref=" private/new-id ",
        live_selfie_ref=" private/new-selfie ",
    )

    identity.refresh_from_db()
    assert updated == identity
    assert identity.national_id_number == "009"
    assert identity.national_id_photo_ref == "private/new-id"
    assert identity.live_selfie_ref == "private/new-selfie"


@pytest.mark.parametrize("field", ["national_id_photo_ref", "live_selfie_ref"])
def test_evidence_reference_helper_accepts_opaque_refs_and_trims_whitespace(field):
    assert normalize_evidence_reference(" private/evidence-key-123 ", field_name=field) == "private/evidence-key-123"


@pytest.mark.parametrize("field", ["national_id_photo_ref", "live_selfie_ref"])
@pytest.mark.parametrize("value", INVALID_EVIDENCE_REFS)
def test_evidence_reference_helper_rejects_invalid_refs(field, value):
    with pytest.raises(ValidationError):
        normalize_evidence_reference(value, field_name=field)


@pytest.mark.parametrize("field", ["national_id_photo_ref", "live_selfie_ref"])
@pytest.mark.parametrize("value", INVALID_EVIDENCE_REFS)
def test_service_create_rejects_invalid_evidence_refs(field, value):
    user = lister_user()

    with pytest.raises(ValidationError) as exc_info:
        create_lister_identity(user=user, national_id_number="001", **{field: value})

    assert "SECRET_IMAGE_PAYLOAD" not in str(exc_info.value)
    assert ListerIdentity.objects.filter(user=user).count() == 0


@pytest.mark.parametrize("field", ["national_id_photo_ref", "live_selfie_ref"])
@pytest.mark.parametrize("value", INVALID_EVIDENCE_REFS)
def test_service_update_rejects_invalid_evidence_refs(field, value):
    user = lister_user()
    identity = create_lister_identity(user=user, national_id_number="001")

    with pytest.raises(ValidationError) as exc_info:
        update_lister_identity(user=user, **{field: value})

    assert "SECRET_IMAGE_PAYLOAD" not in str(exc_info.value)
    identity.refresh_from_db()
    assert getattr(identity, field) == ""


def test_service_update_ignores_workflow_fields():
    user = lister_user()
    identity = create_lister_identity(user=user, national_id_number="001")
    attempted_reviewed_at = timezone.now()

    update_lister_identity(
        user=user,
        status=ListerIdentity.Status.APPROVED,
        submitted_at=attempted_reviewed_at,
        reviewed_at=attempted_reviewed_at,
        reviewed_by=user,
        review_reason="client controlled",
        expires_at=attempted_reviewed_at,
        national_id_number="002",
    )

    identity.refresh_from_db()
    assert identity.national_id_number == "002"
    assert identity.status == ListerIdentity.Status.PENDING
    assert identity.submitted_at is None
    assert identity.reviewed_at is None
    assert identity.reviewed_by is None
    assert identity.review_reason == ""
    assert identity.expires_at is None


@pytest.mark.parametrize(
    "status,submitted",
    [
        (ListerIdentity.Status.PENDING, True),
        (ListerIdentity.Status.APPROVED, False),
        (ListerIdentity.Status.REJECTED, False),
        (ListerIdentity.Status.EXPIRED, False),
    ],
)
def test_service_update_denied_after_submit_or_terminal_status(status, submitted):
    user = lister_user()
    identity = create_lister_identity(user=user, national_id_number="001")
    identity.status = status
    if submitted:
        identity.submitted_at = timezone.now()
    identity.save(update_fields=["status", "submitted_at", "updated_at"])

    with pytest.raises(ValidationError):
        update_lister_identity(user=user, national_id_number="002")


def test_service_update_other_user_identity_denied():
    owner = lister_user()
    other = lister_user(ROLE_AGENT)
    other_identity = create_lister_identity(user=other, national_id_number="001")

    with pytest.raises(PermissionDenied):
        update_lister_identity(user=owner, identity=other_identity, national_id_number="002")


def test_service_submit_complete_identity_succeeds_once():
    user = lister_user()
    identity = create_complete_identity(user)

    submitted = submit_lister_identity(user=user)

    assert submitted.status == ListerIdentity.Status.PENDING
    assert submitted.submitted_at is not None
    assert submitted.reviewed_at is None
    assert submitted.reviewed_by is None
    assert submitted.review_reason == ""
    assert submitted.expires_at is None
    with pytest.raises(ValidationError):
        submit_lister_identity(user=user)


@pytest.mark.parametrize(
    "field",
    ["national_id_number", "national_id_photo_ref", "live_selfie_ref"],
)
def test_service_submit_requires_all_evidence_non_blank(field):
    user = lister_user()
    identity = create_lister_identity(
        user=user,
        national_id_number="001234",
        national_id_photo_ref="private/id",
        live_selfie_ref="private/selfie",
    )
    setattr(identity, field, "   ")
    identity.save(update_fields=[field, "updated_at"])

    with pytest.raises(ValidationError):
        submit_lister_identity(user=user)


@pytest.mark.parametrize("field", ["national_id_photo_ref", "live_selfie_ref"])
@pytest.mark.parametrize(
    "value",
    [
        "https://example.test/id.jpg",
        "data:image/png;base64,SECRET_IMAGE_PAYLOAD",
        "../private/id-photo",
        "x" * 501,
    ],
)
def test_service_submit_revalidates_persisted_evidence_refs(field, value):
    user = lister_user()
    identity = create_complete_identity(user)
    setattr(identity, field, value)
    identity.save(update_fields=[field, "updated_at"])

    with pytest.raises(ValidationError) as exc_info:
        submit_lister_identity(user=user)

    assert "SECRET_IMAGE_PAYLOAD" not in str(exc_info.value)
    identity.refresh_from_db()
    assert identity.submitted_at is None


def test_service_submit_requires_own_identity_and_active_lister_role():
    owner = lister_user()
    other = lister_user(ROLE_AGENT)
    other_identity = create_complete_identity(other)

    with pytest.raises(PermissionDenied):
        submit_lister_identity(user=owner, identity=other_identity)

    assignment = UserRole.objects.get(user=other, role__code=ROLE_AGENT)
    assignment.is_active = False
    assignment.save(update_fields=["is_active"])
    assert not user_has_role(other, ROLE_AGENT)
    with pytest.raises(PermissionDenied):
        submit_lister_identity(user=other)


def test_management_can_approve_submitted_identity():
    manager = management_user()
    owner = lister_user()
    identity = create_submitted_identity(owner)
    original_submitted_at = identity.submitted_at
    original_evidence = (
        identity.national_id_number,
        identity.national_id_photo_ref,
        identity.live_selfie_ref,
    )

    reviewed = approve_lister_identity(identity=identity, reviewed_by=manager)

    assert reviewed.status == ListerIdentity.Status.APPROVED
    assert reviewed.reviewed_at is not None
    assert reviewed.reviewed_by == manager
    assert reviewed.review_reason == ""
    assert reviewed.submitted_at == original_submitted_at
    assert reviewed.expires_at is not None
    assert (
        reviewed.national_id_number,
        reviewed.national_id_photo_ref,
        reviewed.live_selfie_ref,
    ) == original_evidence


def test_management_can_reject_submitted_identity_with_trimmed_reason():
    manager = management_user()
    identity = create_submitted_identity(lister_user())
    original_submitted_at = identity.submitted_at

    reviewed = reject_lister_identity(identity=identity, reviewed_by=manager, reason="  ID photo is unclear  ")

    assert reviewed.status == ListerIdentity.Status.REJECTED
    assert reviewed.reviewed_at is not None
    assert reviewed.reviewed_by == manager
    assert reviewed.review_reason == "ID photo is unclear"
    assert reviewed.submitted_at == original_submitted_at
    assert reviewed.expires_at is None


@pytest.mark.parametrize(
    "role_code",
    [
        ROLE_BUYER,
        ROLE_OWNER,
        ROLE_AGENT,
        ROLE_VERIFIER,
        ROLE_MARKETER,
        ROLE_PROFESSIONAL,
        ROLE_LOCAL_OFFICIAL,
    ],
)
def test_review_denied_for_non_management_roles(role_code):
    actor = lister_user(role_code) if role_code in {ROLE_OWNER, ROLE_AGENT} else create_user()
    if role_code not in {ROLE_OWNER, ROLE_AGENT}:
        grant_role(actor, role_code)
    identity = create_submitted_identity(lister_user())

    with pytest.raises(PermissionDenied):
        approve_lister_identity(identity=identity, reviewed_by=actor)
    with pytest.raises(PermissionDenied):
        reject_lister_identity(identity=identity, reviewed_by=actor, reason="No")


def test_review_denied_for_unauthenticated_unpersisted_inactive_management_and_fake_claims():
    identity = create_submitted_identity(lister_user())
    inactive_assignment = create_user()
    grant_role(inactive_assignment, ROLE_MANAGEMENT, active=False)
    inactive_role = management_user()
    Role.objects.filter(code=ROLE_MANAGEMENT).update(is_active=False)
    fake_claim_user = create_user()
    fake_claim_user.role = ROLE_MANAGEMENT
    fake_claim_user.roles = [ROLE_MANAGEMENT]
    unsaved = get_user_model()(email="unsaved-manager@example.test")

    for actor in (AnonymousUser(), unsaved, inactive_assignment, inactive_role, fake_claim_user):
        with pytest.raises(PermissionDenied):
            approve_lister_identity(identity=identity, reviewed_by=actor)


def test_review_requires_submitted_pending_identity():
    manager = management_user()
    unsubmitted = create_complete_identity(lister_user())
    approved = approve_lister_identity(identity=create_submitted_identity(lister_user()), reviewed_by=manager)
    rejected = reject_lister_identity(
        identity=create_submitted_identity(lister_user()),
        reviewed_by=manager,
        reason="Invalid",
    )
    expired = create_submitted_identity(lister_user())
    expired.status = ListerIdentity.Status.EXPIRED
    expired.save(update_fields=["status", "updated_at"])

    for identity in (unsubmitted, approved, rejected, expired):
        previous_reviewed_at = identity.reviewed_at
        with pytest.raises(ValidationError):
            approve_lister_identity(identity=identity, reviewed_by=manager)
        identity.refresh_from_db()
        assert identity.reviewed_at == previous_reviewed_at


def test_reject_requires_reason():
    manager = management_user()

    for reason in (None, "", "   "):
        with pytest.raises(ValidationError):
            reject_lister_identity(identity=create_submitted_identity(lister_user()), reviewed_by=manager, reason=reason)


def test_management_user_cannot_review_own_identity():
    owner_manager = create_user()
    grant_role(owner_manager, ROLE_OWNER)
    grant_role(owner_manager, ROLE_MANAGEMENT)
    identity = create_submitted_identity(owner_manager)

    with pytest.raises(PermissionDenied):
        approve_lister_identity(identity=identity, reviewed_by=owner_manager)
    identity.refresh_from_db()
    assert identity.expires_at is None
    with pytest.raises(PermissionDenied):
        reject_lister_identity(identity=identity, reviewed_by=owner_manager, reason="No self review")


def test_approval_revalidates_persisted_evidence_but_rejection_can_handle_malformed_submission():
    manager = management_user()
    identity = create_submitted_identity(lister_user())
    identity.national_id_photo_ref = "https://example.test/id.jpg"
    identity.save(update_fields=["national_id_photo_ref", "updated_at"])

    with pytest.raises(ValidationError):
        approve_lister_identity(identity=identity, reviewed_by=manager)
    identity.refresh_from_db()
    assert identity.status == ListerIdentity.Status.PENDING
    assert identity.reviewed_at is None
    assert identity.expires_at is None

    rejected = reject_lister_identity(identity=identity, reviewed_by=manager, reason="Malformed evidence reference")
    assert rejected.status == ListerIdentity.Status.REJECTED
    assert rejected.review_reason == "Malformed evidence reference"


def test_repeated_or_conflicting_review_is_denied_without_mutating_review_state():
    manager = management_user()
    approved = approve_lister_identity(identity=create_submitted_identity(lister_user()), reviewed_by=manager)
    approved_reviewed_at = approved.reviewed_at
    rejected = reject_lister_identity(
        identity=create_submitted_identity(lister_user()),
        reviewed_by=manager,
        reason="Invalid",
    )
    rejected_reviewed_at = rejected.reviewed_at

    with pytest.raises(ValidationError):
        approve_lister_identity(identity=approved, reviewed_by=manager)
    with pytest.raises(ValidationError):
        reject_lister_identity(identity=approved, reviewed_by=manager, reason="No")
    with pytest.raises(ValidationError):
        approve_lister_identity(identity=rejected, reviewed_by=manager)
    with pytest.raises(ValidationError):
        reject_lister_identity(identity=rejected, reviewed_by=manager, reason="No")

    approved.refresh_from_db()
    rejected.refresh_from_db()
    assert approved.reviewed_at == approved_reviewed_at
    assert rejected.reviewed_at == rejected_reviewed_at
