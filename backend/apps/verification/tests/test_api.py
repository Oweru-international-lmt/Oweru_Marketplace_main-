import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.roles.catalog import ROLE_LOCAL_OFFICIAL, ROLE_MANAGEMENT, ROLE_OWNER, ROLE_VERIFIER
from apps.verification.models import PropertyVerification

from .test_document_lifecycle import create_property, create_user, document_evidence, grant_role, owner_with_level_one, verifier
from .test_field_lifecycle import field_evidence, level_two_property, local_official


pytestmark = pytest.mark.django_db


def api_client(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


def document_submission_url(property_record):
    return f"/api/v1/verifications/properties/{property_record.property_id}/documents/"


def field_submission_url(property_record):
    return f"/api/v1/verifications/properties/{property_record.property_id}/field/"


def property_status_url(property_record):
    return f"/api/v1/verifications/properties/{property_record.property_id}/"


def document_detail_url(verification):
    return f"/api/v1/management/verifications/documents/{verification.pk}/"


def field_detail_url(verification):
    return f"/api/v1/management/verifications/field/{verification.pk}/"


def assert_private_evidence_is_absent(payload):
    serialized = str(payload)
    assert "evidence_ref" not in serialized
    assert "private/" not in serialized
    assert "reviewed_by" not in serialized
    assert "rejection_reason" not in serialized
    assert "subject_snapshot" not in serialized


def test_document_submission_requires_authenticated_authorized_level_one_actor_and_rejects_mass_assignment():
    owner = owner_with_level_one()
    property_record = create_property(owner)
    payload = {"evidence": document_evidence()}

    assert api_client().post(document_submission_url(property_record), payload, format="json").status_code == 401

    other_owner = owner_with_level_one()
    assert api_client(other_owner).post(document_submission_url(property_record), payload, format="json").status_code == 403

    response = api_client(owner).post(
        document_submission_url(property_record),
        {**payload, "status": PropertyVerification.Status.APPROVED, "reviewed_by": str(other_owner.pk)},
        format="json",
    )
    assert response.status_code == 400
    assert PropertyVerification.objects.count() == 0

    response = api_client(owner).post(document_submission_url(property_record), payload, format="json")
    assert response.status_code == 201
    assert set(response.data) == {"id", "kind", "status", "submitted_at", "reviewed_at", "expires_at"}
    assert response.data["kind"] == PropertyVerification.Kind.DOCUMENT
    assert_private_evidence_is_absent(response.data)

    no_identity = create_user()
    grant_role(no_identity, ROLE_OWNER)
    no_identity_property = create_property(no_identity)
    response = api_client(no_identity).post(document_submission_url(no_identity_property), payload, format="json")
    assert response.status_code == 400

    invalid = api_client(owner).post(
        document_submission_url(create_property(owner)),
        {"evidence": [{"evidence_type": "TITLE_DOCUMENT", "evidence_ref": "https://example.test/private"}]},
        format="json",
    )
    assert invalid.status_code == 400


def test_field_submission_requires_level_two_and_uses_an_explicit_evidence_allowlist():
    owner = owner_with_level_one()
    property_record = create_property(owner)
    response = api_client(owner).post(field_submission_url(property_record), {"evidence": field_evidence()}, format="json")
    assert response.status_code == 400

    owner, property_record, _ = level_two_property()
    response = api_client(owner).post(
        field_submission_url(property_record),
        {
            "evidence": [{"evidence_type": "TITLE_DOCUMENT", "evidence_ref": "private/not-field-evidence"}],
            "expires_at": "2030-01-01T00:00:00Z",
        },
        format="json",
    )
    assert response.status_code == 400
    assert PropertyVerification.objects.filter(property=property_record, kind=PropertyVerification.Kind.FIELD).count() == 0

    response = api_client(owner).post(field_submission_url(property_record), {"evidence": field_evidence()}, format="json")
    assert response.status_code == 201
    assert response.data["kind"] == PropertyVerification.Kind.FIELD
    assert_private_evidence_is_absent(response.data)


def test_authorized_property_actor_reads_safe_status_and_derived_level_only():
    owner, property_record, document = level_two_property()
    response = api_client(owner).get(property_status_url(property_record))
    assert response.status_code == 200
    assert response.data["effective_verification_level"] == 2
    assert response.data["verifications"][0]["id"] == str(document.pk)
    assert_private_evidence_is_absent(response.data)

    assert api_client(owner_with_level_one()).get(property_status_url(property_record)).status_code == 403
    assert api_client().get(property_status_url(property_record)).status_code == 401


def test_document_review_queue_and_actions_require_only_active_canonical_verifiers():
    owner = owner_with_level_one()
    property_record = create_property(owner)
    submitted = api_client(owner).post(document_submission_url(property_record), {"evidence": document_evidence()}, format="json")
    assert submitted.status_code == 201
    verification = PropertyVerification.objects.get(pk=submitted.data["id"])

    management = create_user()
    grant_role(management, ROLE_MANAGEMENT)
    official = local_official()
    inactive_verifier = create_user()
    grant_role(inactive_verifier, ROLE_VERIFIER, active=False)
    fake_verifier = create_user()
    fake_verifier.role = ROLE_VERIFIER
    fake_verifier.jwt_claim = ROLE_VERIFIER

    for user in (management, official, inactive_verifier, fake_verifier):
        assert api_client(user).get("/api/v1/management/verifications/documents/").status_code == 403
        assert api_client(user).post(f"{document_detail_url(verification)}approve/", {}, format="json").status_code == 403

    reviewer = verifier()
    queued = api_client(reviewer).get("/api/v1/management/verifications/documents/?page_size=1")
    assert queued.status_code == 200
    assert queued.data["count"] == 1
    assert len(queued.data["results"]) == 1
    assert queued.data["results"][0]["id"] == str(verification.pk)
    assert_private_evidence_is_absent(queued.data)

    detail = api_client(reviewer).get(document_detail_url(verification))
    assert detail.status_code == 200
    assert_private_evidence_is_absent(detail.data)

    approve = api_client(reviewer).post(f"{document_detail_url(verification)}approve/", {}, format="json")
    assert approve.status_code == 200
    assert approve.data["status"] == PropertyVerification.Status.APPROVED
    revoke = api_client(reviewer).post(f"{document_detail_url(verification)}revoke/", {}, format="json")
    assert revoke.status_code == 200
    assert revoke.data["status"] == PropertyVerification.Status.REVOKED

    rejected = api_client(owner).post(document_submission_url(property_record), {"evidence": document_evidence("private/retry")}, format="json")
    assert rejected.status_code == 201
    reject = api_client(reviewer).post(
        f"{document_detail_url(PropertyVerification.objects.get(pk=rejected.data['id']))}reject/",
        {"reason": "Missing required details"},
        format="json",
    )
    assert reject.status_code == 200
    assert reject.data["status"] == PropertyVerification.Status.REJECTED


def test_field_review_queue_isolated_to_active_canonical_local_officials():
    owner, property_record, _ = level_two_property()
    submitted = api_client(owner).post(field_submission_url(property_record), {"evidence": field_evidence()}, format="json")
    assert submitted.status_code == 201
    verification = PropertyVerification.objects.get(pk=submitted.data["id"])

    for user in (verifier(), create_user()):
        assert api_client(user).get("/api/v1/management/verifications/field/").status_code == 403

    management = create_user()
    grant_role(management, ROLE_MANAGEMENT)
    assert api_client(management).get("/api/v1/management/verifications/field/").status_code == 403

    inactive_official = create_user()
    grant_role(inactive_official, ROLE_LOCAL_OFFICIAL, active=False)
    assert api_client(inactive_official).get("/api/v1/management/verifications/field/").status_code == 403

    official = local_official()
    queue = api_client(official).get("/api/v1/management/verifications/field/?page_size=1")
    assert queue.status_code == 200
    assert queue.data["count"] == 1
    assert queue.data["results"][0]["id"] == str(verification.pk)
    assert_private_evidence_is_absent(queue.data)
    assert api_client(verifier()).get(document_detail_url(verification)).status_code == 404

    approve = api_client(official).post(f"{field_detail_url(verification)}approve/", {}, format="json")
    assert approve.status_code == 200
    revoke = api_client(official).post(f"{field_detail_url(verification)}revoke/", {}, format="json")
    assert revoke.status_code == 200

    rejected = api_client(owner).post(field_submission_url(property_record), {"evidence": field_evidence("private/field-retry")}, format="json")
    assert rejected.status_code == 201
    reject = api_client(official).post(
        f"{field_detail_url(PropertyVerification.objects.get(pk=rejected.data['id']))}reject/",
        {"reason": "Field report is incomplete"},
        format="json",
    )
    assert reject.status_code == 200
    assert reject.data["status"] == PropertyVerification.Status.REJECTED


def test_review_queues_are_kind_isolated_deterministic_bounded_and_evidence_access_fails_closed():
    document_owner = owner_with_level_one()
    first_property = create_property(document_owner)
    second_property = create_property(document_owner)
    first = api_client(document_owner).post(document_submission_url(first_property), {"evidence": document_evidence()}, format="json")
    second = api_client(document_owner).post(
        document_submission_url(second_property), {"evidence": document_evidence("private/second-document")}, format="json"
    )
    assert first.status_code == second.status_code == 201
    document_reviewer = verifier()
    queue = api_client(document_reviewer).get("/api/v1/management/verifications/documents/?page_size=1")
    assert queue.status_code == 200
    assert queue.data["count"] == 2
    assert len(queue.data["results"]) == 1
    assert queue.data["results"][0]["id"] == first.data["id"]
    assert all(item["kind"] == PropertyVerification.Kind.DOCUMENT for item in queue.data["results"])

    verification = PropertyVerification.objects.get(pk=first.data["id"])
    evidence_url = f"{document_detail_url(verification)}evidence/"
    assert api_client(document_reviewer).get(evidence_url).status_code == 404
    assert api_client().get(evidence_url).status_code == 404
    assert not AuditLog.objects.filter(action="sensitive_data.accessed").exists()


def test_review_endpoints_fail_closed_for_staff_claims_wrong_kinds_and_server_controlled_fields():
    owner = owner_with_level_one()
    property_record = create_property(owner)
    pending = api_client(owner).post(
        document_submission_url(property_record),
        {"evidence": document_evidence()},
        format="json",
    )
    assert pending.status_code == 201
    verification = PropertyVerification.objects.get(pk=pending.data["id"])

    privileged_without_role = create_user()
    privileged_without_role.is_staff = True
    privileged_without_role.is_superuser = True
    privileged_without_role.save(update_fields=["is_staff", "is_superuser"])
    for path in (
        "/api/v1/management/verifications/documents/",
        "/api/v1/management/verifications/field/",
    ):
        assert api_client(privileged_without_role).get(path).status_code == 403
    assert api_client(privileged_without_role).post(
        f"{document_detail_url(verification)}approve/",
        {},
        format="json",
    ).status_code == 403

    reviewer = verifier()
    attack_fields = {
        "status": "APPROVED",
        "kind": "FIELD",
        "submitted_by": str(privileged_without_role.pk),
        "reviewed_by": str(privileged_without_role.pk),
        "reviewed_at": "2030-01-01T00:00:00Z",
        "expires_at": "2030-01-01T00:00:00Z",
        "revoked_at": "2030-01-01T00:00:00Z",
        "verification_level": 3,
        "property": str(property_record.pk),
        "property_id": "OWR-ATTACK",
        "is_verified": True,
        "reviewer": str(privileged_without_role.pk),
        "role": ROLE_VERIFIER,
    }
    response = api_client(reviewer).post(f"{document_detail_url(verification)}approve/", attack_fields, format="json")
    assert response.status_code == 400
    verification.refresh_from_db()
    assert verification.status == PropertyVerification.Status.PENDING
    assert verification.reviewed_by is None
    assert verification.expires_at is None

    owner, field_property, _ = level_two_property()
    field_response = api_client(owner).post(field_submission_url(field_property), {"evidence": field_evidence()}, format="json")
    field = PropertyVerification.objects.get(pk=field_response.data["id"])
    assert api_client(reviewer).get(field_detail_url(field)).status_code == 403
    assert api_client(local_official()).get(document_detail_url(verification)).status_code == 403


def test_multiple_persisted_roles_grant_only_their_matching_review_surfaces():
    reviewer = create_user()
    grant_role(reviewer, ROLE_VERIFIER)
    grant_role(reviewer, ROLE_LOCAL_OFFICIAL)

    assert api_client(reviewer).get("/api/v1/management/verifications/documents/").status_code == 200
    assert api_client(reviewer).get("/api/v1/management/verifications/field/").status_code == 200
