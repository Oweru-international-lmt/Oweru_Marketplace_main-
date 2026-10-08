from io import BytesIO

import pytest
from django.contrib.gis.geos import Point, Polygon
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.site_capture.audit_events import SITE_CAPTURE_PROMOTED
from apps.site_capture.models import SiteCapture
from apps.site_capture.services import (
    create_site_capture,
    get_site_capture,
    promote_site_capture,
    remove_site_capture_media,
    submit_site_capture,
    update_site_capture,
    upload_site_capture_image,
)
from apps.verification.audit_events import VERIFICATION_PROPERTY_CHANGE_INVALIDATED
from apps.verification.models import PropertyVerification, PropertyVerificationEvidence
from apps.verification.services import (
    approve_document_verification,
    approve_field_verification,
    get_effective_verification_level,
    submit_document_verification,
    submit_field_verification,
)
from apps.verification.tests.test_document_lifecycle import document_evidence, verifier
from apps.verification.tests.test_field_lifecycle import field_evidence, local_official, submitted_field


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def media_settings():
    with override_settings(
        MEDIA_STORAGE_BACKEND="memory",
        MEDIA_MAX_UPLOAD_BYTES=1024 * 1024,
        MEDIA_ALLOWED_IMAGE_MIME_TYPES=["image/jpeg", "image/png", "image/webp"],
        MEDIA_MAX_IMAGE_WIDTH=80,
        MEDIA_MAX_IMAGE_HEIGHT=60,
    ):
        yield


def image_upload():
    image = Image.new("RGB", (32, 24), color=(90, 120, 150))
    output = BytesIO()
    image.save(output, format="JPEG")
    return SimpleUploadedFile("capture.jpg", output.getvalue(), content_type="image/jpeg")


def level_three_property():
    owner, property_record, _, field = submitted_field()
    approve_field_verification(verification=field, reviewer=local_official())
    assert get_effective_verification_level(user=owner, property_record=property_record) == 2
    return owner, property_record


def submitted_capture(owner, property_record, point=None):
    capture = create_site_capture(
        property_record=property_record,
        actor=owner,
        observed_point=point or Point(39.25, -6.79, srid=4326),
        observed_boundary=Polygon(((39.25, -6.79), (39.251, -6.79), (39.251, -6.789), (39.25, -6.79)), srid=4326),
    )
    return submit_site_capture(site_capture=capture, actor=owner)


def test_site_capture_lifecycle_and_media_do_not_affect_effective_level_or_evidence():
    owner, property_record = level_three_property()
    evidence_ids = set(PropertyVerificationEvidence.objects.values_list("pk", flat=True))
    capture = create_site_capture(
        property_record=property_record,
        actor=owner,
        observed_point=Point(39.25, -6.79, srid=4326),
        observed_boundary=Polygon(((39.25, -6.79), (39.251, -6.79), (39.251, -6.789), (39.25, -6.79)), srid=4326),
    )

    assert get_effective_verification_level(user=owner, property_record=property_record) == 2
    update_site_capture(
        site_capture=capture,
        actor=owner,
        observed_point=Point(39.26, -6.78, srid=4326),
    )
    media = upload_site_capture_image(site_capture=capture, actor=owner, image=image_upload())
    remove_site_capture_media(site_capture=capture, media=media, actor=owner)
    get_site_capture(capture_id=capture.capture_id, actor=owner)
    submit_site_capture(site_capture=capture, actor=owner)

    assert get_effective_verification_level(user=owner, property_record=property_record) == 2
    assert set(PropertyVerificationEvidence.objects.values_list("pk", flat=True)) == evidence_ids
    assert not PropertyVerificationEvidence.objects.filter(evidence_ref=media.media_id).exists()


def test_material_promotion_revokes_level_three_through_canonical_property_invalidation():
    owner, property_record = level_three_property()
    capture = submitted_capture(owner, property_record)
    original_point = capture.observed_point.clone()

    promote_site_capture(site_capture=capture, actor=owner)

    property_record.refresh_from_db()
    capture.refresh_from_db()
    document = property_record.verifications.get(kind=PropertyVerification.Kind.DOCUMENT)
    field = property_record.verifications.get(kind=PropertyVerification.Kind.FIELD)
    assert property_record.pin.equals_exact(original_point, tolerance=0)
    assert capture.observed_point.equals_exact(original_point, tolerance=0)
    assert capture.status == SiteCapture.Status.SUBMITTED
    assert {document.status, field.status} == {PropertyVerification.Status.REVOKED}
    assert get_effective_verification_level(user=owner, property_record=property_record) == 1
    assert AuditLog.objects.filter(action=SITE_CAPTURE_PROMOTED, entity_id=str(capture.pk)).count() == 1
    assert AuditLog.objects.filter(action=VERIFICATION_PROPERTY_CHANGE_INVALIDATED).count() == 2


def test_same_value_promotion_preserves_level_three_without_invalidation():
    owner, property_record = level_three_property()
    capture = submitted_capture(owner, property_record, point=property_record.pin.clone())

    promote_site_capture(site_capture=capture, actor=owner)

    assert get_effective_verification_level(user=owner, property_record=property_record) == 2
    assert not AuditLog.objects.filter(action=SITE_CAPTURE_PROMOTED).exists()
    assert not AuditLog.objects.filter(action=VERIFICATION_PROPERTY_CHANGE_INVALIDATED).exists()


def test_draft_captures_cannot_change_property_or_verification_state():
    owner, property_record = level_three_property()
    original_point = property_record.pin.clone()
    capture = create_site_capture(
        property_record=property_record,
        actor=owner,
        observed_point=Point(39.25, -6.79, srid=4326),
    )

    with pytest.raises(ValidationError):
        promote_site_capture(site_capture=capture, actor=owner)

    property_record.refresh_from_db()
    assert property_record.pin.equals_exact(original_point, tolerance=0)
    assert get_effective_verification_level(user=owner, property_record=property_record) == 2


def test_stale_submitted_capture_reenters_canonical_invalidation_path_on_promotion():
    owner, property_record = level_three_property()
    capture = submitted_capture(owner, property_record)

    from apps.properties.services import update_property_record

    update_property_record(
        actor=owner,
        property_record=property_record,
        pin=Point(39.30, -6.70, srid=4326),
    )
    document = approve_document_verification(
        verification=submit_document_verification(
            property_record=property_record,
            submitted_by=owner,
            evidence=document_evidence("private/stale-document"),
        ),
        reviewer=verifier(),
    )
    field = approve_field_verification(
        verification=submit_field_verification(
            property_record=property_record,
            submitted_by=owner,
            evidence=field_evidence("private/stale-field"),
        ),
        reviewer=local_official(),
    )
    assert get_effective_verification_level(user=owner, property_record=property_record) == 2

    promote_site_capture(site_capture=capture, actor=owner)

    property_record.refresh_from_db()
    capture.refresh_from_db()
    document.refresh_from_db()
    field.refresh_from_db()
    assert property_record.pin.equals_exact(capture.observed_point, tolerance=0)
    assert document.status == PropertyVerification.Status.REVOKED
    assert field.status == PropertyVerification.Status.REVOKED
    assert get_effective_verification_level(user=owner, property_record=property_record) == 1
