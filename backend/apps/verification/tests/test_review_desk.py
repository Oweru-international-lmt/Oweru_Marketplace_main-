import uuid
from datetime import timedelta
from io import BytesIO

import pytest
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import Point
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.media.models import Media
from apps.media.storage import get_private_media_storage
from apps.properties.models import PossibleDuplicate, PropertyRecord
from apps.roles.catalog import ROLE_MANAGEMENT
from apps.verification.models import PropertyVerification
from apps.verification.services import submit_document_verification

from .test_api import assert_private_evidence_is_absent
from .test_document_lifecycle import create_property, create_user, document_evidence, grant_role, owner_with_level_one, verifier


pytestmark = pytest.mark.django_db

DESK = "/api/v1/management/verifications/documents/"
ALL_YES = {"pin_on_land": True, "photos_match": True, "no_conflicting_duplicate": True, "description_fits": True}


def client(user):
    api = APIClient()
    api.force_authenticate(user)
    return api


def title_document(property_record, owner):
    key = f"private/title-{uuid.uuid4().hex}.jpg"
    get_private_media_storage().save_private_object(key=key, content=BytesIO(b"title"), content_type="image/jpeg")
    return Media.objects.create(
        content_type=ContentType.objects.get_for_model(PropertyRecord),
        object_id=property_record.pk,
        uploaded_by=owner,
        file_key=key,
        mime_type="image/jpeg",
        size_bytes=5,
    )


def submitted_check(*, with_document=False):
    owner = owner_with_level_one()
    property_record = create_property(owner)
    reference = title_document(property_record, owner).media_id if with_document else "private/title"
    verification = submit_document_verification(
        property_record=property_record,
        submitted_by=owner,
        evidence=document_evidence(reference),
    )
    return owner, property_record, verification


def test_queue_rows_carry_what_the_desk_shows_without_private_references():
    _, property_record, verification = submitted_check()
    PropertyVerification.objects.filter(pk=verification.pk).update(submitted_at=timezone.now() - timedelta(days=3))

    response = client(verifier()).get(DESK)

    assert response.status_code == 200
    row = response.data["results"][0]
    assert row["id"] == str(verification.pk)
    assert row["property_id"] == property_record.property_id
    assert row["lister_name"] == "Document Verification User"
    assert property_record.ward.name in row["area"]
    assert row["late"] is True
    assert row["duplicate_count"] == 0
    assert_private_evidence_is_absent(response.data)


def test_summary_counts_waiting_late_and_this_months_decisions():
    reviewer = verifier()
    _, _, waiting = submitted_check()
    _, _, late = submitted_check()
    PropertyVerification.objects.filter(pk=late.pk).update(submitted_at=timezone.now() - timedelta(days=3))
    _, _, failed = submitted_check()
    assert client(reviewer).post(f"{DESK}{failed.pk}/reject/", {"reason": "Pin is in the sea."}, format="json").status_code == 200

    response = client(reviewer).get(f"{DESK}summary/")

    assert response.status_code == 200
    assert response.data == {"waiting": 2, "late": 1, "passed_this_month": 0, "failed_this_month": 1}
    decided = client(reviewer).get(f"{DESK}?state=decided")
    assert [row["id"] for row in decided.data["results"]] == [str(failed.pk)]


def test_check_screen_shows_pin_documents_and_duplicates_but_no_private_references():
    owner, property_record, verification = submitted_check()
    neighbour = create_property(owner)
    PossibleDuplicate.objects.create(property_a=property_record, property_b=neighbour, signals=["PIN_PROXIMITY"], distance_meters=40)

    response = client(verifier()).get(f"{DESK}{verification.pk}/")

    assert response.status_code == 200
    assert response.data["pin"] == {"lat": property_record.pin.y, "lng": property_record.pin.x}
    assert response.data["documents"][0]["evidence_type"] == "TITLE_DOCUMENT"
    assert response.data["duplicates"][0]["property_id"] == neighbour.property_id
    assert response.data["checklist"] == ["pin_on_land", "photos_match", "no_conflicting_duplicate", "description_fits"]
    assert_private_evidence_is_absent(response.data)


def test_title_document_link_is_for_verifiers_and_recorded_as_sensitive_access():
    _, _, verification = submitted_check(with_document=True)
    document_id = verification.evidence.get().pk
    url = f"{DESK}{verification.pk}/evidence/{document_id}/"

    management = create_user()
    grant_role(management, ROLE_MANAGEMENT)
    assert client(management).get(url).status_code == 403

    response = client(verifier()).get(url)

    assert response.status_code == 200
    assert response.data["url"]
    assert response.data["mime_type"] == "image/jpeg"
    assert AuditLog.objects.filter(
        entity_id=str(verification.pk), action="sensitive_data.accessed",
        after__access_type="verification_title_document",
    ).count() == 1
    assert client(verifier()).get(f"{DESK}{verification.pk}/evidence/{uuid.uuid4()}/").status_code == 404


def test_title_document_from_another_property_is_not_served():
    owner = owner_with_level_one()
    property_record = create_property(owner)
    stray = title_document(create_property(owner), owner)
    verification = submit_document_verification(
        property_record=property_record, submitted_by=owner, evidence=document_evidence(stray.media_id),
    )

    url = f"{DESK}{verification.pk}/evidence/{verification.evidence.get().pk}/"

    assert client(verifier()).get(url).status_code == 404


def test_pass_needs_every_point_and_records_the_answers():
    _, _, verification = submitted_check()
    reviewer = verifier()

    refused = client(reviewer).post(f"{DESK}{verification.pk}/approve/", {"checklist": {**ALL_YES, "photos_match": False}}, format="json")
    assert refused.status_code == 400
    assert client(reviewer).post(f"{DESK}{verification.pk}/approve/", {"checklist": {"pin_on_land": True}}, format="json").status_code == 400

    passed = client(reviewer).post(f"{DESK}{verification.pk}/approve/", {"checklist": ALL_YES}, format="json")

    assert passed.status_code == 200
    assert passed.data["status"] == PropertyVerification.Status.APPROVED
    log = AuditLog.objects.get(entity_id=str(verification.pk), action__endswith="approved")
    assert log.after["checklist"] == ALL_YES


def test_fail_keeps_the_reason_and_the_answers():
    _, _, verification = submitted_check()
    answers = {**ALL_YES, "no_conflicting_duplicate": False}

    failed = client(verifier()).post(
        f"{DESK}{verification.pk}/reject/", {"reason": "Same plot as OWR-1.", "checklist": answers}, format="json",
    )

    assert failed.status_code == 200
    assert failed.data["reason"] == "Same plot as OWR-1."
    log = AuditLog.objects.get(entity_id=str(verification.pk), action__endswith="rejected")
    assert log.after["checklist"] == answers


def test_lister_reads_the_reason_for_a_failed_check_and_can_send_again():
    owner, property_record, verification = submitted_check()
    status_url = f"/api/v1/verifications/properties/{property_record.property_id}/"
    assert client(owner).get(status_url).data["verifications"][0]["reason"] is None

    client(verifier()).post(f"{DESK}{verification.pk}/reject/", {"reason": "Pin is in the sea."}, format="json")

    latest = client(owner).get(status_url).data["verifications"][0]
    assert latest["status"] == PropertyVerification.Status.REJECTED
    assert latest["reason"] == "Pin is in the sea."
    retry = client(owner).post(
        f"/api/v1/verifications/properties/{property_record.property_id}/documents/",
        {"evidence": document_evidence("private/retry")},
        format="json",
    )
    assert retry.status_code == 201


SCANNED_PDF = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n"


def jpeg_bytes():
    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, "JPEG")
    return buffer.getvalue()


def test_lister_uploads_a_scanned_pdf_or_a_photo_and_the_verifier_opens_it():
    from django.core.files.uploadedfile import SimpleUploadedFile

    owner = owner_with_level_one()
    property_record = create_property(owner)
    url = f"/api/v1/verifications/properties/{property_record.property_id}/title-documents/"

    stranger = owner_with_level_one()
    pdf = SimpleUploadedFile("hati.pdf", SCANNED_PDF, content_type="application/pdf")
    assert client(stranger).post(url, {"document": pdf}, format="multipart").status_code == 403

    renamed = SimpleUploadedFile("hati.jpg", SCANNED_PDF, content_type="image/jpeg")
    assert client(owner).post(url, {"document": renamed}, format="multipart").status_code == 400
    broken = SimpleUploadedFile("hati.pdf", b"%PDF-1.4 no end marker", content_type="application/pdf")
    assert client(owner).post(url, {"document": broken}, format="multipart").status_code == 400

    photo = SimpleUploadedFile("hati.jpg", jpeg_bytes(), content_type="image/jpeg")
    assert client(owner).post(url, {"document": photo}, format="multipart").data["mime_type"] == "image/jpeg"

    pdf = SimpleUploadedFile("hati.pdf", SCANNED_PDF, content_type="application/pdf")
    uploaded = client(owner).post(url, {"document": pdf}, format="multipart")
    assert uploaded.status_code == 201
    assert uploaded.data["mime_type"] == "application/pdf"

    sent = client(owner).post(
        f"/api/v1/verifications/properties/{property_record.property_id}/documents/",
        {"evidence": document_evidence(uploaded.data["media_id"])},
        format="json",
    )
    assert sent.status_code == 201
    verification = PropertyVerification.objects.get(pk=sent.data["id"])
    opened = client(verifier()).get(f"{DESK}{verification.pk}/evidence/{verification.evidence.get().pk}/")
    assert opened.status_code == 200
    assert opened.data["mime_type"] == "application/pdf"
