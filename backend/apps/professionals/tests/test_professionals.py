from datetime import timedelta
from unittest.mock import patch
import uuid
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.leads.tests.test_leads import grant
from apps.roles.models import Role, UserRole
from apps.roles.services import bootstrap_canonical_roles
from apps.verification.models import VerificationJob, VerificationTask, FullCheckReceipt, OwnerConsent, PropertyRelationship, TaskSubmission
from apps.verification.task_services import submit_task, reopen_task
from apps.payments.documents import save_document
from apps.media.storage import reset_in_memory_storage
from apps.verification.tests.test_models_services import create_property
from apps.professionals.models import ProfessionalProfile
from apps.professionals.services import register_professional, update_professional, eligible_professionals, assign_professional, decide_task

pytestmark = pytest.mark.django_db


def account(role):
    token = uuid.uuid4().hex
    user = User.objects.create_user(email=f"{token}@example.test", phone=f"+2557{int(token[:8], 16) % 100000000:08d}", full_name=f"Test {role}", password="StrongPass123!", account_category="public" if role in {"buyer", "owner", "agent"} else "operational")
    grant(user, role)
    bootstrap_canonical_roles()
    UserRole.objects.create(user=user, role=Role.objects.get(code=role))
    return user


def pdf():
    return SimpleUploadedFile("report.pdf", b"%PDF-1.4\nAudit test fixture\n%%EOF", content_type="application/pdf")


@pytest.fixture(autouse=True)
def storage():
    reset_in_memory_storage()
    with override_settings(MEDIA_STORAGE_BACKEND="memory"):
        yield
    reset_in_memory_storage()


@pytest.fixture
def setup():
    manager, verifier, buyer, owner = [account(role) for role in ["management", "verifier", "buyer", "owner"]]
    property_record = create_property(owner)
    job = VerificationJob.objects.create(property=property_record, buyer=buyer, owner_user=owner, owner_name=owner.full_name, owner_phone=owner.phone, kind="FULL", verifier=verifier, status="IN_PROGRESS", fee=100000, scope_snapshot={"scope": "Full Check"}, subject_snapshot={})
    media = save_document(actor=manager, owner=job, upload=pdf())
    FullCheckReceipt.objects.create(job=job, actor=manager, amount=job.fee, bank_reference="BANK", tax_receipt_number=uuid.uuid4().hex, tax_receipt=media)
    OwnerConsent.objects.create(job=job, actor=owner, decision="CONFIRM", recipient_phone=owner.phone, context={})
    profile = register_professional(actor=manager, professional_type="PLANNER", registration_number=uuid.uuid4().hex, national_id_number="PRIVATE-NATIONAL-ID", districts=[property_record.district], email=f"{uuid.uuid4().hex}@example.test", phone=f"+2558{uuid.uuid4().int % 100000000:08d}", full_name="Registered Planner")
    task = VerificationTask.objects.create(job=job, kind="PROFESSIONAL", professional_type="PLANNER")
    return manager, verifier, owner, property_record, job, profile, task


def findings():
    return {"layout": "Layout reviewed", "development_restrictions": "Recorded restrictions", "planning_context": "Context reviewed"}


def test_declared_relationship_returns_task_to_verifier_and_blocks_reassignment(setup):
    _, verifier, _, _, _, profile, task = setup
    assign_professional(actor=verifier, task_id=task.pk, profile_id=profile.pk)
    from apps.verification.relationships import declare_task_relationship
    declaration = declare_task_relationship(actor=profile.user, task_id=task.pk, reason="Related to the Owner")
    task.refresh_from_db()
    assert task.status == "UNASSIGNED" and task.assignee_id is None
    assert declare_task_relationship(actor=profile.user, task_id=task.pk, reason="Same relationship").pk == declaration.pk
    with pytest.raises(PermissionDenied):
        assign_professional(actor=verifier, task_id=task.pk, profile_id=profile.pk)
    assert AuditLog.objects.filter(action="verification.relationship_declared", entity_id=declaration.pk).count() == 1


def test_other_professional_cannot_declare_relationship_on_private_task(setup):
    _, verifier, _, _, _, profile, task = setup
    assign_professional(actor=verifier, task_id=task.pk, profile_id=profile.pk)
    from apps.verification.relationships import declare_task_relationship
    with pytest.raises(PermissionDenied):
        declare_task_relationship(actor=account("professional"), task_id=task.pk, reason="Unrelated private task")


def test_outside_owner_contact_cannot_be_assigned_as_professional(setup):
    _, verifier, _, _, job, profile, task = setup
    # Consent has already frozen its owner context, so build this conflict as
    # a distinct outside order rather than editing the historical consent.
    from apps.verification.models import VerificationJob, VerificationTask
    other = VerificationJob.objects.create(property=job.property, buyer=account("buyer"), owner_phone=profile.user.phone, owner_name=profile.user.full_name, kind="OUTSIDE_FULL", verifier=verifier, status="IN_PROGRESS", fee=100000, scope_snapshot={}, subject_snapshot={})
    from apps.verification.conflicts import has_property_conflict
    assert has_property_conflict(profile.user, other.property)
    assert profile not in eligible_professionals(property_record=other.property, professional_type="PLANNER")
    with pytest.raises(PermissionDenied):
        assign_professional(actor=verifier, task_id=task.pk, profile_id=profile.pk)


def test_verified_owner_identity_on_another_account_is_conflicted(setup):
    manager, verifier, owner, prop, _, profile, task = setup
    from apps.lister_identity.models import ListerIdentity
    now = timezone.now()
    ListerIdentity.objects.create(user=owner, national_id_number=profile.national_id_number, national_id_photo_ref="private/id-card", live_selfie_ref="private/live-selfie", status="APPROVED", submitted_at=now, reviewed_by=manager, reviewed_at=now, expires_at=now + timedelta(days=365))
    with pytest.raises(PermissionDenied):
        assign_professional(actor=verifier, task_id=task.pk, profile_id=profile.pk)


def accepted(setup):
    _, verifier, _, _, _, profile, task = setup
    assign_professional(actor=verifier, task_id=task.pk, profile_id=profile.pk)
    decide_task(actor=profile.user, task_id=task.pk, decision="ACCEPT")
    return profile, task


@pytest.mark.parametrize("professional_type", ProfessionalProfile.Type.values)
def test_registers_exact_srd_types_and_partner_roles(setup, professional_type):
    manager, _, _, property_record, _, _, _ = setup
    profile = register_professional(actor=manager, professional_type=professional_type, registration_number=uuid.uuid4().hex, national_id_number="ID", regions=[property_record.region], user=account("professional"))
    assert profile.user.has_role("professional")
    assert profile.user.account_category == "operational"
    assert profile.verified_by == manager
    assert profile.regions.get() == property_record.region


@pytest.mark.parametrize("bad_type", ["ENGINEER", "LAWYER", "", "PLANNER_FAKE"])
def test_rejects_invented_types(setup, bad_type):
    manager, _, _, property_record, _, _, _ = setup
    with pytest.raises(ValidationError):
        register_professional(actor=manager, professional_type=bad_type, registration_number="REG", national_id_number="ID", districts=[property_record.district], user=account("professional"))


def test_registration_api_is_management_only_and_omits_private_fields(setup):
    manager, _, owner, prop, _, _, _ = setup
    payload = {"professional_type": "SURVEYOR", "registration_number": "SURVEY-NEW", "national_id_number": "VERY-PRIVATE-ID", "districts": [str(prop.district_id)], "email": "new-surveyor@example.test", "phone": "+255700123451", "full_name": "Surveyor"}
    client = APIClient()
    client.force_authenticate(owner)
    assert client.post("/api/v1/management/professionals/", payload, format="json").status_code == 403
    client.force_authenticate(manager)
    response = client.post("/api/v1/management/professionals/", payload, format="json")
    assert response.status_code == 201
    assert "national_id_number" not in response.data
    assert "password" not in repr(response.data)
    assert client.post("/api/v1/management/professionals/", {**payload, "verification_level": 3}, format="json").status_code == 400


@pytest.mark.parametrize("conflict", ["creator", "declared", "owner_phone"])
def test_conflicts_block_assignment(setup, conflict):
    _, verifier, _, prop, job, profile, task = setup
    if conflict == "creator":
        prop.created_by = profile.user
        prop.save(update_fields=["created_by"])
    elif conflict == "declared":
        PropertyRelationship.objects.create(property=prop, user=profile.user, reason="Relative of owner")
    else:
        from apps.listings.tests.test_services import create_listing_for
        from apps.payments.models import OwnerContact
        listing = create_listing_for(prop.created_by, status="ACTIVE")
        listing.property = prop
        listing.save(update_fields=["property"])
        OwnerContact.objects.create(listing=listing, name="Owner", whatsapp=profile.user.phone)
    with pytest.raises(PermissionDenied):
        assign_professional(actor=verifier, task_id=task.pk, profile_id=profile.pk)


@pytest.mark.parametrize("defect", ["inactive", "wrong_type", "wrong_district", "role_revoked"])
def test_eligibility_rechecks_type_coverage_and_persisted_status(setup, defect):
    manager, verifier, _, prop, _, profile, task = setup
    if defect == "inactive":
        update_professional(actor=manager, profile_id=profile.pk, status="INACTIVE", reason="Suspended")
    elif defect == "wrong_type":
        profile.professional_type = "SURVEYOR"
        profile.save()
    elif defect == "wrong_district":
        profile.districts.clear()
    else:
        profile.user.user_roles.update(is_active=False)
    with pytest.raises(PermissionDenied):
        assign_professional(actor=verifier, task_id=task.pk, profile_id=profile.pk)


def test_accept_decline_and_reassignment_keep_history(setup):
    manager, verifier, _, prop, _, profile, task = setup
    assign_professional(actor=verifier, task_id=task.pk, profile_id=profile.pk)
    decide_task(actor=profile.user, task_id=task.pk, decision="DECLINE", reason="Unavailable")
    task.refresh_from_db()
    assert task.status == "UNASSIGNED" and task.assignee_id is None
    assign_professional(actor=verifier, task_id=task.pk, profile_id=profile.pk)
    decide_task(actor=profile.user, task_id=task.pk, decision="ACCEPT")
    assert task.assignment_history.count() == 4
    assert AuditLog.objects.filter(action="professional.task_declined", entity_id=str(task.pk)).count() == 1


def test_professional_cannot_accept_someone_elses_task(setup):
    _, verifier, _, _, _, profile, task = setup
    assign_professional(actor=verifier, task_id=task.pk, profile_id=profile.pk)
    with pytest.raises(PermissionDenied):
        decide_task(actor=account("professional"), task_id=task.pk, decision="ACCEPT")


def test_locked_submission_preserves_name_and_registration_snapshot(setup):
    manager, _, _, _, job, _, _ = setup
    profile, task = accepted(setup)
    submission = submit_task(actor=profile.user, task_id=task.pk, findings=findings(), report=pdf(), device="phone")
    original = submission.registration_number
    update_professional(actor=manager, profile_id=profile.pk, registration_number="CHANGED-REG")
    submission.refresh_from_db()
    assert submission.registration_number == original
    assert submission.author_name == "Registered Planner"
    with pytest.raises(ValidationError):
        submission.delete()
    with pytest.raises(ValidationError):
        TaskSubmission.objects.filter(pk=submission.pk).update(findings={})
    job.refresh_from_db()
    assert job.status == "UNDER_REVIEW"
    from apps.verification.services import get_effective_verification_level
    assert get_effective_verification_level(user=profile.user, property_record=job.property) != 3


def test_correction_is_new_version_not_overwrite(setup):
    _, verifier, _, _, _, _, _ = setup
    profile, task = accepted(setup)
    first = submit_task(actor=profile.user, task_id=task.pk, findings=findings(), report=pdf(), device="phone")
    reopen_task(actor=verifier, task_id=task.pk, reason="Clarify restrictions")
    second = submit_task(actor=profile.user, task_id=task.pk, findings={**findings(), "development_restrictions": "Clarified"}, report=pdf(), device="phone")
    assert second.version == 2 and second.supersedes_id == first.pk
    assert task.submissions.count() == 2
    first.refresh_from_db()
    assert first.findings["development_restrictions"] == "Recorded restrictions"


@pytest.mark.parametrize("bad", ["missing_report", "not_accepted", "expired", "conflict"])
def test_submission_prerequisites_are_server_enforced(setup, bad):
    _, verifier, _, prop, _, profile, task = setup
    assign_professional(actor=verifier, task_id=task.pk, profile_id=profile.pk)
    if bad != "not_accepted":
        decide_task(actor=profile.user, task_id=task.pk, decision="ACCEPT")
    if bad == "expired":
        VerificationTask.objects.filter(pk=task.pk).update(due_at=timezone.now() - timedelta(seconds=1))
    if bad == "conflict":
        PropertyRelationship.objects.create(property=prop, user=profile.user, reason="Owner relative")
    with pytest.raises((ValidationError, PermissionDenied)):
        submit_task(actor=profile.user, task_id=task.pk, findings=findings(), report=None if bad == "missing_report" else pdf(), device="phone")
    assert not task.submissions.exists()


def test_private_task_and_report_object_isolation(setup):
    _, _, owner, _, _, _, _ = setup
    profile, task = accepted(setup)
    submission = submit_task(actor=profile.user, task_id=task.pk, findings=findings(), report=pdf(), device="phone")
    client = APIClient()
    for stranger in [owner, account("buyer"), account("professional")]:
        client.force_authenticate(stranger)
        assert client.get(f"/api/v1/verification-tasks/{task.pk}/").status_code == 403
        assert client.get(f"/api/v1/verification-tasks/submissions/{submission.pk}/report/").status_code == 403
    client.force_authenticate(profile.user)
    response = client.get(f"/api/v1/verification-tasks/submissions/{submission.pk}/report/")
    assert response.status_code == 200 and "url" in response.data
    assert "financial/" not in repr(response.data)
    assert client.patch(f"/api/v1/verification-tasks/{task.pk}/", {"status": "SUBMITTED"}, format="json").status_code == 405


def test_audit_failure_rolls_back_submission_and_private_object(setup):
    from apps.media.storage import get_private_media_storage
    profile, task = accepted(setup)
    before = set(get_private_media_storage().objects)
    with patch("apps.verification.task_services.create_audit_log", side_effect=RuntimeError("audit unavailable")):
        with pytest.raises(RuntimeError):
            submit_task(actor=profile.user, task_id=task.pk, findings=findings(), report=pdf(), device="phone")
    assert not task.submissions.exists()
    task.refresh_from_db()
    assert task.status == "ACCEPTED"
    assert set(get_private_media_storage().objects) == before
