from datetime import timedelta
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.lister_identity.models import ListerIdentity
from apps.lister_identity.services import approve_lister_identity, create_lister_identity, submit_lister_identity
from apps.roles.catalog import ROLE_AGENT, ROLE_BUYER, ROLE_MANAGEMENT, ROLE_OWNER, ROLE_VERIFIER
from apps.roles.models import Role, UserRole
from apps.roles.services import bootstrap_canonical_roles


pytestmark = pytest.mark.django_db

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


def create_user(email=None):
    suffix = uuid.uuid4().hex[:10]
    return get_user_model().objects.create_user(
        email=email or f"api-{suffix}@example.test",
        phone=f"+255{uuid.uuid4().int % 1000000000:09d}",
        full_name="Synthetic Lister",
        password="StrongPass123!",
    )


def grant_role(user, role_code):
    bootstrap_canonical_roles()
    role = Role.objects.get(code=role_code)
    return UserRole.objects.create(user=user, role=role, assigned_by=user)


def authenticated_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def lister_user(role_code=ROLE_OWNER):
    user = create_user()
    grant_role(user, role_code)
    return user


def management_user():
    user = create_user()
    grant_role(user, ROLE_MANAGEMENT)
    return user


def complete_payload(**extra):
    data = {
        "national_id_number": "001234567890",
        "national_id_photo_ref": "private/id-photo",
        "live_selfie_ref": "private/selfie",
    }
    data.update(extra)
    return data


def create_submitted_identity(user=None):
    user = user or lister_user()
    identity = create_lister_identity(user=user, **complete_payload())
    return submit_lister_identity(user=user, identity=identity)


def create_verified_identity(user=None):
    return approve_lister_identity(identity=create_submitted_identity(user), reviewed_by=management_user())


def assert_sensitive_fields_absent(data):
    rendered = repr(data).lower()
    forbidden = [
        "password",
        "token",
        "jwt",
        "refresh",
        "access",
        "reviewed_by",
        "reviewer",
        "email",
        "phone",
    ]
    for value in forbidden:
        assert value not in rendered


def test_api_create_requires_authentication_and_active_lister_role():
    assert APIClient().post("/api/v1/lister-identity/", complete_payload(), format="json").status_code == 401

    buyer = create_user()
    grant_role(buyer, ROLE_BUYER)
    response = authenticated_client(buyer).post("/api/v1/lister-identity/", complete_payload(), format="json")

    assert response.status_code == 403


@pytest.mark.parametrize("role_code", [ROLE_OWNER, ROLE_AGENT])
def test_api_create_lister_identity_for_owner_or_agent(role_code):
    user = lister_user(role_code)

    response = authenticated_client(user).post(
        "/api/v1/lister-identity/",
        complete_payload(national_id_number=" 001234 "),
        format="json",
    )

    assert response.status_code == 201
    assert response.data["national_id_number"] == "001234"
    assert response.data["status"] == ListerIdentity.Status.PENDING
    assert response.data["submitted_at"] is None
    assert_sensitive_fields_absent(response.data)


def test_api_create_duplicate_returns_safe_error():
    user = lister_user()
    client = authenticated_client(user)
    assert client.post("/api/v1/lister-identity/", complete_payload(), format="json").status_code == 201

    response = client.post("/api/v1/lister-identity/", complete_payload(), format="json")

    assert response.status_code == 400
    assert ListerIdentity.objects.filter(user=user).count() == 1


@pytest.mark.parametrize("field", ["national_id_photo_ref", "live_selfie_ref"])
@pytest.mark.parametrize("value", INVALID_EVIDENCE_REFS)
def test_api_create_rejects_invalid_evidence_refs_without_echoing_payload(field, value):
    user = lister_user()

    response = authenticated_client(user).post(
        "/api/v1/lister-identity/",
        complete_payload(**{field: value}),
        format="json",
    )

    assert response.status_code == 400
    assert "SECRET_IMAGE_PAYLOAD" not in repr(response.data)
    assert ListerIdentity.objects.filter(user=user).count() == 0


def test_api_create_ignores_client_controlled_workflow_fields():
    user = lister_user()
    reviewer = create_user()
    response = authenticated_client(user).post(
        "/api/v1/lister-identity/",
        {
            **complete_payload(),
            "status": ListerIdentity.Status.APPROVED,
            "submitted_at": timezone.now().isoformat(),
            "reviewed_at": timezone.now().isoformat(),
            "reviewed_by": str(reviewer.pk),
            "review_reason": "approved by client",
            "expires_at": timezone.now().isoformat(),
        },
        format="json",
    )

    identity = ListerIdentity.objects.get(user=user)
    assert response.status_code == 201
    assert identity.status == ListerIdentity.Status.PENDING
    assert identity.submitted_at is None
    assert identity.reviewed_at is None
    assert identity.reviewed_by is None
    assert identity.review_reason == ""
    assert identity.expires_at is None


def test_api_get_me_requires_authentication_existing_identity_and_lister_role():
    assert APIClient().get("/api/v1/lister-identity/me/").status_code == 401

    buyer = create_user()
    grant_role(buyer, ROLE_BUYER)
    assert authenticated_client(buyer).get("/api/v1/lister-identity/me/").status_code == 403

    owner = lister_user()
    assert authenticated_client(owner).get("/api/v1/lister-identity/me/").status_code == 404

    identity = create_lister_identity(user=owner, **complete_payload())
    response = authenticated_client(owner).get("/api/v1/lister-identity/me/")

    assert response.status_code == 200
    assert response.data["id"] == str(identity.pk)
    assert_sensitive_fields_absent(response.data)


def test_api_patch_updates_allowed_fields_only_before_submit():
    user = lister_user()
    create_lister_identity(user=user, national_id_number="001")

    response = authenticated_client(user).patch(
        "/api/v1/lister-identity/me/",
        {
            "national_id_number": " 009 ",
            "national_id_photo_ref": " private/new-id ",
            "live_selfie_ref": " private/new-selfie ",
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.data["national_id_number"] == "009"
    assert response.data["national_id_photo_ref"] == "private/new-id"
    assert response.data["live_selfie_ref"] == "private/new-selfie"


@pytest.mark.parametrize("field", ["national_id_photo_ref", "live_selfie_ref"])
@pytest.mark.parametrize("value", INVALID_EVIDENCE_REFS)
def test_api_patch_rejects_invalid_evidence_refs_without_echoing_payload(field, value):
    user = lister_user()
    identity = create_lister_identity(user=user, national_id_number="001")

    response = authenticated_client(user).patch(
        "/api/v1/lister-identity/me/",
        {field: value},
        format="json",
    )

    assert response.status_code == 400
    assert "SECRET_IMAGE_PAYLOAD" not in repr(response.data)
    identity.refresh_from_db()
    assert getattr(identity, field) == ""


def test_api_patch_denied_when_unauthenticated_or_not_lister():
    assert APIClient().patch("/api/v1/lister-identity/me/", {"national_id_number": "1"}, format="json").status_code == 401

    buyer = create_user()
    grant_role(buyer, ROLE_BUYER)
    response = authenticated_client(buyer).patch("/api/v1/lister-identity/me/", {"national_id_number": "1"}, format="json")

    assert response.status_code == 403


def test_api_patch_ignores_protected_workflow_fields():
    user = lister_user()
    reviewer = create_user()
    identity = create_lister_identity(user=user, national_id_number="001")

    response = authenticated_client(user).patch(
        "/api/v1/lister-identity/me/",
        {
            "status": ListerIdentity.Status.APPROVED,
            "submitted_at": timezone.now().isoformat(),
            "reviewed_at": timezone.now().isoformat(),
            "reviewed_by": str(reviewer.pk),
            "review_reason": "client text",
            "expires_at": timezone.now().isoformat(),
            "national_id_number": "002",
        },
        format="json",
    )

    identity.refresh_from_db()
    assert response.status_code == 200
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
def test_api_patch_denied_after_submit_or_review_state(status, submitted):
    user = lister_user()
    identity = create_lister_identity(user=user, national_id_number="001")
    identity.status = status
    if submitted:
        identity.submitted_at = timezone.now()
    identity.save(update_fields=["status", "submitted_at", "updated_at"])

    response = authenticated_client(user).patch(
        "/api/v1/lister-identity/me/",
        {"national_id_number": "002"},
        format="json",
    )

    assert response.status_code == 400


def test_api_submit_requires_authentication_role_and_complete_evidence():
    assert APIClient().post("/api/v1/lister-identity/me/submit/", {}, format="json").status_code == 401

    buyer = create_user()
    grant_role(buyer, ROLE_BUYER)
    assert authenticated_client(buyer).post("/api/v1/lister-identity/me/submit/", {}, format="json").status_code == 403

    owner = lister_user()
    create_lister_identity(user=owner, national_id_number="001")
    response = authenticated_client(owner).post("/api/v1/lister-identity/me/submit/", {}, format="json")

    assert response.status_code == 400


def test_api_submit_complete_identity_sets_submitted_at_once():
    user = lister_user()
    create_lister_identity(user=user, **complete_payload())
    client = authenticated_client(user)

    response = client.post("/api/v1/lister-identity/me/submit/", {}, format="json")

    assert response.status_code == 200
    assert response.data["status"] == ListerIdentity.Status.PENDING
    assert response.data["submitted_at"] is not None
    assert response.data["reviewed_at"] is None
    assert response.data["review_reason"] == ""
    assert response.data["expires_at"] is None
    assert_sensitive_fields_absent(response.data)

    original_submitted_at = ListerIdentity.objects.get(user=user).submitted_at
    repeated = client.post("/api/v1/lister-identity/me/submit/", {}, format="json")
    assert repeated.status_code == 400
    assert ListerIdentity.objects.get(user=user).submitted_at == original_submitted_at


def test_api_users_cannot_affect_another_identity_through_me_endpoints():
    owner = lister_user()
    other = lister_user(ROLE_AGENT)
    other_identity = create_lister_identity(user=other, **complete_payload())

    response = authenticated_client(owner).patch(
        "/api/v1/lister-identity/me/",
        {"national_id_number": "999"},
        format="json",
    )

    other_identity.refresh_from_db()
    assert response.status_code == 404
    assert other_identity.national_id_number == "001234567890"


def test_management_queue_requires_management_and_excludes_non_reviewable_identities():
    submitted = create_submitted_identity()
    unsubmitted = create_lister_identity(user=lister_user(), **complete_payload(national_id_number="002"))
    approved = create_submitted_identity()
    approved.status = ListerIdentity.Status.APPROVED
    approved.reviewed_at = timezone.now()
    approved.reviewed_by = management_user()
    approved.save(update_fields=["status", "reviewed_at", "reviewed_by", "updated_at"])
    rejected = create_submitted_identity()
    rejected.status = ListerIdentity.Status.REJECTED
    rejected.reviewed_at = timezone.now()
    rejected.reviewed_by = approved.reviewed_by
    rejected.review_reason = "No"
    rejected.save(update_fields=["status", "reviewed_at", "reviewed_by", "review_reason", "updated_at"])
    expired = create_submitted_identity()
    expired.status = ListerIdentity.Status.EXPIRED
    expired.save(update_fields=["status", "updated_at"])

    assert APIClient().get("/api/v1/management/lister-identities/").status_code == 401
    verifier = create_user()
    grant_role(verifier, ROLE_VERIFIER)
    assert authenticated_client(verifier).get("/api/v1/management/lister-identities/").status_code == 403
    buyer = create_user()
    grant_role(buyer, ROLE_BUYER)
    assert authenticated_client(buyer).get("/api/v1/management/lister-identities/").status_code == 403

    response = authenticated_client(management_user()).get("/api/v1/management/lister-identities/")

    assert response.status_code == 200
    ids = {item["id"] for item in response.data}
    assert str(submitted.pk) in ids
    assert str(unsubmitted.pk) not in ids
    assert str(approved.pk) not in ids
    assert str(rejected.pk) not in ids
    assert str(expired.pk) not in ids


def test_management_detail_requires_management_and_constrains_sensitive_response():
    identity = create_submitted_identity()
    manager = management_user()

    assert APIClient().get(f"/api/v1/management/lister-identities/{identity.pk}/").status_code == 401
    verifier = create_user()
    grant_role(verifier, ROLE_VERIFIER)
    assert authenticated_client(verifier).get(f"/api/v1/management/lister-identities/{identity.pk}/").status_code == 403

    response = authenticated_client(manager).get(f"/api/v1/management/lister-identities/{identity.pk}/")

    assert response.status_code == 200
    assert response.data["id"] == str(identity.pk)
    assert response.data["user_id"] == str(identity.user_id)
    assert response.data["user_full_name"] == identity.user.full_name
    assert response.data["national_id_photo_ref"] == "private/id-photo"
    assert "email" not in response.data
    assert "phone" not in response.data
    assert "password" not in repr(response.data).lower()
    assert "token" not in repr(response.data).lower()


def test_management_detail_nonexistent_uuid_returns_404():
    response = authenticated_client(management_user()).get(
        "/api/v1/management/lister-identities/00000000-0000-0000-0000-000000000000/"
    )

    assert response.status_code == 404


def test_management_approve_endpoint_transitions_submitted_identity_and_ignores_client_workflow_fields():
    manager = management_user()
    identity = create_submitted_identity()
    original_submitted_at = identity.submitted_at

    response = authenticated_client(manager).post(
        f"/api/v1/management/lister-identities/{identity.pk}/approve/",
        {
            "status": ListerIdentity.Status.REJECTED,
            "reviewed_by": str(identity.user_id),
            "reviewed_at": timezone.now().isoformat(),
            "expires_at": timezone.now().isoformat(),
            "national_id_number": "999",
            "national_id_photo_ref": "private/changed",
            "live_selfie_ref": "private/changed",
        },
        format="json",
    )

    identity.refresh_from_db()
    assert response.status_code == 200
    assert identity.status == ListerIdentity.Status.APPROVED
    assert identity.reviewed_by == manager
    assert identity.reviewed_at is not None
    assert identity.review_reason == ""
    assert identity.submitted_at == original_submitted_at
    assert identity.expires_at is not None
    assert identity.national_id_number == "001234567890"
    assert identity.national_id_photo_ref == "private/id-photo"


def test_management_approve_denies_unsubmitted_unauthorized_self_and_repeated_review():
    manager = management_user()
    unsubmitted = create_lister_identity(user=lister_user(), **complete_payload())
    verifier = create_user()
    grant_role(verifier, ROLE_VERIFIER)
    own_manager = create_user()
    grant_role(own_manager, ROLE_OWNER)
    grant_role(own_manager, ROLE_MANAGEMENT)
    own_identity = create_submitted_identity(own_manager)

    assert authenticated_client(verifier).post(
        f"/api/v1/management/lister-identities/{unsubmitted.pk}/approve/",
        {},
        format="json",
    ).status_code == 403
    assert authenticated_client(manager).post(
        f"/api/v1/management/lister-identities/{unsubmitted.pk}/approve/",
        {},
        format="json",
    ).status_code == 400
    assert authenticated_client(own_manager).post(
        f"/api/v1/management/lister-identities/{own_identity.pk}/approve/",
        {},
        format="json",
    ).status_code == 403

    reviewed = create_submitted_identity()
    assert authenticated_client(manager).post(
        f"/api/v1/management/lister-identities/{reviewed.pk}/approve/",
        {},
        format="json",
    ).status_code == 200
    assert authenticated_client(manager).post(
        f"/api/v1/management/lister-identities/{reviewed.pk}/approve/",
        {},
        format="json",
    ).status_code == 400


def test_management_reject_endpoint_requires_reason_and_ignores_client_workflow_fields():
    manager = management_user()
    identity = create_submitted_identity()

    blank = authenticated_client(manager).post(
        f"/api/v1/management/lister-identities/{identity.pk}/reject/",
        {"reason": "   "},
        format="json",
    )
    assert blank.status_code == 400

    response = authenticated_client(manager).post(
        f"/api/v1/management/lister-identities/{identity.pk}/reject/",
        {
            "reason": "  ID photo unreadable  ",
            "status": ListerIdentity.Status.APPROVED,
            "reviewed_by": str(identity.user_id),
            "reviewed_at": timezone.now().isoformat(),
            "expires_at": timezone.now().isoformat(),
            "national_id_number": "999",
            "national_id_photo_ref": "private/changed",
            "live_selfie_ref": "private/changed",
        },
        format="json",
    )

    identity.refresh_from_db()
    assert response.status_code == 200
    assert identity.status == ListerIdentity.Status.REJECTED
    assert identity.reviewed_by == manager
    assert identity.review_reason == "ID photo unreadable"
    assert identity.expires_at is None
    assert identity.national_id_number == "001234567890"
    assert identity.national_id_photo_ref == "private/id-photo"


def test_management_reject_denies_unauthorized_self_and_repeated_review():
    manager = management_user()
    verifier = create_user()
    grant_role(verifier, ROLE_VERIFIER)
    identity = create_submitted_identity()
    own_manager = create_user()
    grant_role(own_manager, ROLE_OWNER)
    grant_role(own_manager, ROLE_MANAGEMENT)
    own_identity = create_submitted_identity(own_manager)

    assert authenticated_client(verifier).post(
        f"/api/v1/management/lister-identities/{identity.pk}/reject/",
        {"reason": "No"},
        format="json",
    ).status_code == 403
    assert authenticated_client(own_manager).post(
        f"/api/v1/management/lister-identities/{own_identity.pk}/reject/",
        {"reason": "No self review"},
        format="json",
    ).status_code == 403
    assert authenticated_client(manager).post(
        f"/api/v1/management/lister-identities/{identity.pk}/reject/",
        {"reason": "No"},
        format="json",
    ).status_code == 200
    assert authenticated_client(manager).post(
        f"/api/v1/management/lister-identities/{identity.pk}/reject/",
        {"reason": "No again"},
        format="json",
    ).status_code == 400


def assert_public_profile_response_is_safe(data):
    assert set(data) == {"id", "name", "is_verified", "lister_roles", "member_since"}
    rendered = repr(data).lower()
    forbidden = [
        "national_id_number",
        "national_id_photo_ref",
        "live_selfie_ref",
        "submitted_at",
        "reviewed_at",
        "reviewed_by",
        "review_reason",
        "expires_at",
        "email",
        "phone",
        "password",
        "jwt",
        "refresh",
        "reset",
        "verification",
        "locked_until",
        "failed_login",
        "private/id-photo",
        "private/selfie",
    ]
    for value in forbidden:
        assert value not in rendered


def test_public_lister_profile_is_public_for_verified_owner_and_authenticated_users():
    user = lister_user(ROLE_OWNER)
    identity = create_verified_identity(user)

    anonymous_response = APIClient().get(f"/api/v1/listers/{identity.pk}/")
    auth_response = authenticated_client(create_user()).get(f"/api/v1/listers/{identity.pk}/")

    for response in (anonymous_response, auth_response):
        assert response.status_code == 200
        assert response.data["id"] == str(identity.pk)
        assert response.data["name"] == user.full_name
        assert response.data["is_verified"] is True
        assert response.data["lister_roles"] == [ROLE_OWNER]
        assert response.data["member_since"] is not None
        assert_public_profile_response_is_safe(response.data)


@pytest.mark.parametrize(
    "status,expires_at",
    [
        (ListerIdentity.Status.PENDING, None),
        (ListerIdentity.Status.REJECTED, None),
        (ListerIdentity.Status.EXPIRED, timezone.now()),
        (ListerIdentity.Status.APPROVED, None),
        (ListerIdentity.Status.APPROVED, timezone.now()),
        (ListerIdentity.Status.APPROVED, timezone.now() - timedelta(seconds=1)),
    ],
)
def test_public_lister_profile_hidden_when_not_currently_verified(status, expires_at):
    identity = create_verified_identity(lister_user())
    identity.status = status
    identity.expires_at = expires_at
    identity.save(update_fields=["status", "expires_at", "updated_at"])

    response = APIClient().get(f"/api/v1/listers/{identity.pk}/")

    assert response.status_code == 404


def test_public_lister_profile_owner_agent_roles_come_from_active_canonical_rbac():
    owner = lister_user(ROLE_OWNER)
    owner_identity = create_verified_identity(owner)
    assert APIClient().get(f"/api/v1/listers/{owner_identity.pk}/").data["lister_roles"] == [ROLE_OWNER]

    agent = lister_user(ROLE_AGENT)
    agent_identity = create_verified_identity(agent)
    assert APIClient().get(f"/api/v1/listers/{agent_identity.pk}/").data["lister_roles"] == [ROLE_AGENT]

    both = create_user()
    grant_role(both, ROLE_OWNER)
    grant_role(both, ROLE_AGENT)
    both_identity = create_verified_identity(both)
    assert APIClient().get(f"/api/v1/listers/{both_identity.pk}/").data["lister_roles"] == [ROLE_OWNER, ROLE_AGENT]


def test_public_lister_profile_hidden_without_active_lister_role_or_active_account():
    buyer_only = lister_user(ROLE_OWNER)
    buyer_only_identity = create_verified_identity(buyer_only)
    UserRole.objects.filter(user=buyer_only, role__code=ROLE_OWNER).update(is_active=False)
    grant_role(buyer_only, ROLE_BUYER)
    assert APIClient().get(f"/api/v1/listers/{buyer_only_identity.pk}/").status_code == 404

    inactive_assignment_user = lister_user(ROLE_OWNER)
    inactive_assignment_identity = create_verified_identity(inactive_assignment_user)
    UserRole.objects.filter(user=inactive_assignment_user, role__code=ROLE_OWNER).update(is_active=False)
    assert APIClient().get(f"/api/v1/listers/{inactive_assignment_identity.pk}/").status_code == 404

    inactive_role_user = lister_user(ROLE_AGENT)
    inactive_role_identity = create_verified_identity(inactive_role_user)
    Role.objects.filter(code=ROLE_AGENT).update(is_active=False)
    assert APIClient().get(f"/api/v1/listers/{inactive_role_identity.pk}/").status_code == 404

    inactive_account = lister_user(ROLE_OWNER)
    inactive_account_identity = create_verified_identity(inactive_account)
    inactive_account.is_active = False
    inactive_account.save(update_fields=["is_active"])
    assert APIClient().get(f"/api/v1/listers/{inactive_account_identity.pk}/").status_code == 404


def test_public_lister_profile_ignores_client_or_jwt_role_spoofing():
    user = lister_user(ROLE_OWNER)
    hidden_identity = create_verified_identity(user)
    UserRole.objects.filter(user=user, role__code=ROLE_OWNER).update(is_active=False)
    user.role = ROLE_OWNER
    user.roles = [ROLE_OWNER, ROLE_AGENT]
    assert APIClient().get(f"/api/v1/listers/{hidden_identity.pk}/").status_code == 404

    owner = lister_user(ROLE_OWNER)
    owner.role = ROLE_AGENT
    owner.roles = [ROLE_AGENT]
    visible_identity = create_verified_identity(owner)
    response = APIClient().get(f"/api/v1/listers/{visible_identity.pk}/")

    assert response.status_code == 200
    assert response.data["lister_roles"] == [ROLE_OWNER]


def test_public_lister_profile_nonexistent_uuid_returns_404():
    response = APIClient().get("/api/v1/listers/00000000-0000-0000-0000-000000000000/")

    assert response.status_code == 404


def test_public_lister_profile_does_not_invent_photo_areas_or_property_types():
    identity = create_verified_identity(lister_user())

    response = APIClient().get(f"/api/v1/listers/{identity.pk}/")

    assert response.status_code == 200
    assert "photo" not in response.data
    assert "profile_photo" not in response.data
    assert "areas_covered" not in response.data
    assert "property_types" not in response.data
    assert identity.national_id_photo_ref != response.data.get("photo")
    assert identity.live_selfie_ref != response.data.get("photo")
