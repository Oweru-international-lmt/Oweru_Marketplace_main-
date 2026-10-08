import pytest
from django.contrib.gis.geos import Point
from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.professionals.tests.test_professionals import account, pdf, storage
from apps.professionals.services import register_professional, assign_professional, decide_task, update_professional
from apps.local_officials.full_check import revoke_locality, assign_locality
from apps.site_capture.evidence import upload_capture_asset
from apps.site_capture.services import create_site_capture
from apps.verification.models import VerificationJob
from apps.verification import full_check_services as services
from apps.verification.task_services import submit_task
from .test_full_check import workflow, paid, valid_capture, official_answers
from apps.site_capture.tests.test_capture_provenance import image_file

pytestmark = pytest.mark.django_db


def partner(workflow, type):
    prop = workflow[5].property
    return register_professional(actor=workflow[0], professional_type=type, registration_number=f"{type}-REG", national_id_number="PRIVATE-ID", districts=[prop.district], user=account("professional"))


def test_surveyor_can_capture_without_general_property_edit_and_complete_full_check(workflow):
    manager, verifier, buyer, owner, official, listing, _ = workflow
    job = paid(workflow)
    services.owner_consent(actor=owner, job_id=job.pk, decision="CONFIRM")
    services.start_tasks(actor=verifier, job_id=job.pk, professional_types=["SURVEYOR", "AFISA_MIPANGO_MIJI"], surveyor_capture=True)
    surveyor = partner(workflow, "SURVEYOR")
    afisa = partner(workflow, "AFISA_MIPANGO_MIJI")
    task = job.tasks.get(professional_type="SURVEYOR")
    assign_professional(actor=verifier, task_id=task.pk, profile_id=surveyor.pk)
    decide_task(actor=surveyor.user, task_id=task.pk, decision="ACCEPT")
    from apps.properties.policies import can_update_property_record
    assert not can_update_property_record(surveyor.user, job.property)
    draft = create_site_capture(actor=surveyor.user, property_record=job.property, observed_point=job.property.pin)
    upload_capture_asset(actor=surveyor.user, site_capture=draft, file=image_file(), source="CAMERA", device="phone")
    from apps.site_capture.services import record_corner, submit_site_capture
    from django.utils import timezone
    lon, lat = job.property.pin.x, job.property.pin.y
    for x, y in [(lon, lat), (lon + .0003, lat), (lon + .0003, lat + .0003)]:
        record_corner(actor=surveyor.user, site_capture=draft, point=Point(x, y, srid=4326), accuracy_m=5, observed_at=timezone.now(), device="phone")
    capture = submit_site_capture(actor=surveyor.user, site_capture=draft)
    submit_task(actor=surveyor.user, task_id=task.pk, findings={"beacon_photos": "Corner photographs attached", "overlap_notes": "Reviewed recorded overlaps"}, device="phone", report=pdf(), capture=capture)
    afisa_task = job.tasks.get(professional_type="AFISA_MIPANGO_MIJI")
    assign_professional(actor=verifier, task_id=afisa_task.pk, profile_id=afisa.pk)
    decide_task(actor=afisa.user, task_id=afisa_task.pk, decision="ACCEPT")
    submit_task(actor=afisa.user, task_id=afisa_task.pk, findings={"permitted_use": "Use checked", "planned_roads_or_reserves": "Public layers reviewed", "supporting_extracts": "Planning extracts in report"}, device="phone", report=pdf())
    submit_task(actor=official, task_id=job.tasks.get(kind="LOCAL_OFFICE").pk, findings=official_answers(), device="phone", report=pdf(), signed_and_stamped=True)
    submit_task(actor=verifier, task_id=job.tasks.get(kind="REGISTRY").pk, findings={"search_result": "Registry records checked", "reference": "REGISTRY"}, device="staff", report=pdf())
    assert services.finalize_full_check(actor=verifier, job_id=job.pk, result="PASSED", risk_assessment="All required evidence reviewed")["status"] == "PASSED"


def test_surveyor_losing_current_type_or_coverage_cannot_capture(workflow):
    job = paid(workflow)
    services.owner_consent(actor=workflow[3], job_id=job.pk, decision="CONFIRM")
    services.start_tasks(actor=workflow[1], job_id=job.pk, professional_types=["SURVEYOR"], surveyor_capture=True)
    profile = partner(workflow, "SURVEYOR")
    task = job.tasks.get(kind="PROFESSIONAL")
    assign_professional(actor=workflow[1], task_id=task.pk, profile_id=profile.pk)
    decide_task(actor=profile.user, task_id=task.pk, decision="ACCEPT")
    profile.districts.clear()
    with pytest.raises(PermissionDenied):
        create_site_capture(actor=profile.user, property_record=job.property, observed_point=job.property.pin)


def test_outside_property_owner_consent_capture_and_optional_professionals(workflow):
    manager, verifier, buyer, owner, official, listing, _ = workflow
    prop = listing.property
    outside = {"category": prop.category, "pin": {"type": "Point", "coordinates": [39.25, -6.8]}, "region": str(prop.region_id), "district": str(prop.district_id), "ward": str(prop.ward_id), "locality": str(prop.locality_id), "stated_size": "1000", "size_unit": "sqm", "title_type": "NONE"}
    response = services.order_full_check(actor=buyer, outside=outside, owner_user=owner, quote_token=services.quote()["quote"], key="outside")
    job = VerificationJob.objects.get(pk=response["job_id"])
    assert job.kind == "OUTSIDE_FULL" and job.property.created_by_id == buyer.pk
    services.confirm_full_check_payment(actor=manager, job_id=job.pk, amount=job.fee, reference=job.payment_reference, bank_reference="OUTSIDE-BANK", tax_receipt_number="OUTSIDE-TAX", tax_receipt=pdf(), key="paid-outside")
    services.assign_verifier(actor=manager, job_id=job.pk, verifier=verifier)
    services.owner_consent(actor=owner, job_id=job.pk, decision="CONFIRM")
    services.start_tasks(actor=verifier, job_id=job.pk)
    job.refresh_from_db()
    submit_task(actor=owner, task_id=job.tasks.get(kind="SITE_CAPTURE").pk, findings={}, device="owner-phone", capture=valid_capture(owner, job.property))
    submit_task(actor=official, task_id=job.tasks.get(kind="LOCAL_OFFICE").pk, findings=official_answers(), device="official-phone", report=pdf(), signed_and_stamped=True)
    services.finalize_full_check(actor=verifier, job_id=job.pk, result="PASSED", risk_assessment="Untitled land, local records carry less protection")
    assert not job.tasks.filter(kind="REGISTRY").exists()
    from apps.lister_identity.services import get_public_verification_summary
    assert "No registered title" in get_public_verification_summary(user=owner, property_record=job.property)["title_warning"]


def test_official_missing_stamp_or_comment_cannot_submit(workflow):
    from .test_full_check import started
    job = started(workflow)
    submit_task(actor=workflow[3], task_id=job.tasks.get(kind="SITE_CAPTURE").pk, findings={}, device="phone", capture=valid_capture(workflow[3], job.property))
    task = job.tasks.get(kind="LOCAL_OFFICE")
    with pytest.raises(ValidationError):
        submit_task(actor=workflow[4], task_id=task.pk, findings=official_answers(), device="phone", report=pdf())
    answers = official_answers()
    answers["3"]["comment"] = ""
    with pytest.raises(ValidationError):
        submit_task(actor=workflow[4], task_id=task.pk, findings=answers, device="phone", report=pdf(), signed_and_stamped=True)


def test_missing_exact_official_alerts_management_and_later_coverage_routes(workflow):
    from .test_full_check import started
    from apps.local_officials.models import OfficialLocalityCoverage
    from apps.verification.models import VerificationNotice
    coverage = OfficialLocalityCoverage.objects.get(official__user=workflow[4])
    revoke_locality(actor=workflow[0], coverage=coverage)
    job = started(workflow)
    submit_task(actor=workflow[3], task_id=job.tasks.get(kind="SITE_CAPTURE").pk, findings={}, device="phone", capture=valid_capture(workflow[3], job.property))
    task = job.tasks.get(kind="LOCAL_OFFICE")
    assert task.status == "NEEDS_OFFICIAL"
    assert VerificationNotice.objects.filter(task=task, recipient=workflow[0], purpose="NEEDS_OFFICIAL").exists()
    original_deadline = task.due_at
    assign_locality(actor=workflow[0], official=workflow[4].local_official_profile, locality=job.property.locality)
    task.refresh_from_db()
    assert task.status == "ASSIGNED" and task.assignee_id == workflow[4].pk and task.due_at == original_deadline


def test_revoked_official_cannot_submit_and_task_returns_to_needs_official(workflow):
    from .test_full_check import started
    from apps.local_officials.models import OfficialLocalityCoverage
    job = started(workflow)
    submit_task(actor=workflow[3], task_id=job.tasks.get(kind="SITE_CAPTURE").pk, findings={}, device="phone", capture=valid_capture(workflow[3], job.property))
    task = job.tasks.get(kind="LOCAL_OFFICE")
    revoke_locality(actor=workflow[0], coverage=OfficialLocalityCoverage.objects.get(official__user=workflow[4]))
    task.refresh_from_db()
    assert task.status == "NEEDS_OFFICIAL"
    with pytest.raises(PermissionDenied):
        submit_task(actor=workflow[4], task_id=task.pk, findings=official_answers(), device="phone", report=pdf(), signed_and_stamped=True)


def test_surveyor_captures_are_private_to_their_full_check_even_on_same_property(workflow):
    manager, verifier, _, owner, _, _, _ = workflow
    first = paid(workflow)
    services.owner_consent(actor=owner, job_id=first.pk, decision="CONFIRM")
    services.start_tasks(actor=verifier, job_id=first.pk, professional_types=["SURVEYOR"], surveyor_capture=True)
    surveyor_a = partner(workflow, "SURVEYOR")
    first_task = first.tasks.get(kind="PROFESSIONAL")
    assign_professional(actor=verifier, task_id=first_task.pk, profile_id=surveyor_a.pk)
    decide_task(actor=surveyor_a.user, task_id=first_task.pk, decision="ACCEPT")
    capture_a = create_site_capture(actor=surveyor_a.user, property_record=first.property, observed_point=first.property.pin)
    asset = upload_capture_asset(actor=surveyor_a.user, site_capture=capture_a, file=image_file(), source="CAMERA")
    second_workflow = (*workflow[:2], account("buyer"), *workflow[3:])
    second = paid(second_workflow)
    services.owner_consent(actor=owner, job_id=second.pk, decision="CONFIRM")
    services.start_tasks(actor=verifier, job_id=second.pk, professional_types=["SURVEYOR"], surveyor_capture=True)
    surveyor_b = register_professional(actor=manager, professional_type="SURVEYOR", registration_number="SURVEYOR-B-REG", national_id_number="OTHER-ID", districts=[first.property.district], user=account("professional"))
    second_task = second.tasks.get(kind="PROFESSIONAL")
    assign_professional(actor=verifier, task_id=second_task.pk, profile_id=surveyor_b.pk)
    decide_task(actor=surveyor_b.user, task_id=second_task.pk, decision="ACCEPT")
    capture_b = create_site_capture(actor=surveyor_b.user, property_record=second.property, observed_point=second.property.pin)
    from apps.site_capture.services import get_site_capture, get_property_site_captures, update_site_capture
    from apps.media.services import get_media
    assert capture_a.verification_task_id == first_task.pk and capture_b.verification_task_id == second_task.pk
    for outsider in [surveyor_b.user, owner, second_workflow[2]]:
        with pytest.raises(PermissionDenied):
            get_site_capture(actor=outsider, capture_id=capture_a.capture_id)
        with pytest.raises(PermissionDenied):
            get_media(actor=outsider, media_id=asset.media.media_id)
        with pytest.raises(PermissionDenied):
            update_site_capture(actor=outsider, site_capture=capture_a, observed_point=first.property.pin)
    assert list(get_property_site_captures(actor=surveyor_b.user, property_record=first.property)) == [capture_b]
    assert get_site_capture(actor=verifier, capture_id=capture_a.capture_id).pk == capture_a.pk
