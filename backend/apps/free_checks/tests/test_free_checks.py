from datetime import timedelta
from unittest.mock import patch
import pytest
from django.db import connection, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError, Throttled
from rest_framework.test import APIClient
from apps.audit.models import AuditLog
from apps.media.storage import get_private_media_storage
from apps.professionals.tests.test_professionals import storage, account
from apps.payments.tests.test_concurrency import concurrent
from apps.payments.idempotency import Conflict
from apps.verification.configuration import change_setting
from apps.verification.models import VerificationJob
from apps.verification.services import get_effective_verification_level
from apps.properties.models import PropertyRecord
from apps.free_checks.models import FreeCheck, FreeCheckLead
from apps.free_checks import services

pytestmark = pytest.mark.django_db


def inputs(**changes):
    return {"pin": {"type": "Point", "coordinates": [39.2, -6.8]}, "category": "LAND", "size": "100", "size_unit": "sqm", "description": "Residential land near the main road", "phone": "+255712345678", "language": "en", **changes}


def test_anonymous_outside_record_pdf_lead_and_no_level_three():
    check = services.submit(values=inputs(), key="first")
    assert check.property.is_outside_check and check.property.created_by_id is None
    assert check.property.locality_id is None
    assert FreeCheckLead.objects.get(free_check=check).user_id is None
    assert not VerificationJob.objects.exists()
    assert get_effective_verification_level(user=None, property_record=check.property) < 3
    assert services.public_result(check)["disclaimer"] == "This is not ownership verification"
    assert check.verdicts["land"] == "UNAVAILABLE"
    report = check.reports.get()
    content = get_private_media_storage().objects[report.media.file_key]["bytes"]
    assert content.startswith(b"%PDF-")


def test_idempotent_replay_does_not_consume_quota_or_duplicate_report():
    first = services.submit(values=inputs(), key="same")
    second = services.submit(values=inputs(phone="0712345678"), key="same")
    assert first.pk == second.pk and FreeCheck.objects.count() == 1
    assert first.reports.count() == 1
    with pytest.raises(Conflict):
        services.submit(values=inputs(description="Another description"), key="same")


def test_normalized_phone_daily_limit():
    for index in range(5):
        services.submit(values=inputs(), key=str(index))
    with pytest.raises(Throttled):
        services.submit(values=inputs(phone="00255712345678"), key="six")
    assert PropertyRecord.objects.count() == 5


@pytest.mark.parametrize("field,value", [("phone", "123"), ("size", "0"), ("category", "RENT"), ("description", "coordinates 39.2000, -6.8000"), ("description", "GPS boundary"), ("external_url", "file:///private"), ("language", "fr"), ("unknown", "x")])
def test_invalid_submission_has_no_side_effects(field, value):
    with pytest.raises(ValidationError):
        services.submit(values=inputs(**{field: value}), key="bad")
    assert not FreeCheck.objects.exists() and not PropertyRecord.objects.exists()


def test_download_requires_unexpired_object_bound_token():
    check = services.submit(values=inputs(), key="first")
    other = services.submit(values=inputs(phone="+255712345679"), key="second")
    token = services.token_for(check)
    assert services.authorized_check(check.pk, token).pk == check.pk
    with pytest.raises(PermissionDenied):
        services.authorized_check(other.pk, token)
    with patch("apps.free_checks.services.timezone.now", return_value=check.expires_at):
        with pytest.raises(PermissionDenied):
            services.authorized_check(check.pk, token)


def test_public_api_never_exposes_phone_geometry_or_private_keys():
    client = APIClient()
    response = client.post("/api/v1/free-checks/", inputs(), format="json", HTTP_IDEMPOTENCY_KEY="api")
    assert response.status_code == 201
    text = str(response.data)
    for private in ["39.2", "-6.8", "file_key", "token_digest", "email", "boundary"]:
        assert private not in text
    check = FreeCheck.objects.get()
    assert client.get(f"/api/v1/free-checks/{check.pk}/pdf/").status_code == 403
    download = client.get(f"/api/v1/free-checks/{check.pk}/pdf/", {"token": services.token_for(check)})
    assert download.status_code == 200 and download["Cache-Control"] == "no-store"
    assert "whatsapp_link" in response.data


def test_report_swahili_and_history_immutable():
    check = services.submit(values=inputs(language="sw"), key="sw")
    assert services.public_result(check)["disclaimer"] == "Huu si uthibitisho wa umiliki"
    check.description = "changed"
    with pytest.raises(ValidationError):
        check.save()
    with pytest.raises(ValidationError):
        check.reports.all().delete()


def test_private_objects_and_quota_rollback_on_audit_failure():
    with patch("apps.free_checks.services.create_audit_log", side_effect=RuntimeError("audit failed")):
        with pytest.raises(RuntimeError):
            services.submit(values=inputs(), key="failure")
    assert not FreeCheck.objects.exists() and not PropertyRecord.objects.exists()
    assert not get_private_media_storage().objects


def test_management_setting_controls_limit_and_expiry():
    manager = account("management")
    change_setting(actor=manager, key="free_check_daily_limit", value=1)
    change_setting(actor=manager, key="free_check_report_days", value=2)
    check = services.submit(values=inputs(), key="one")
    assert check.expires_at - check.created_at < timedelta(days=2, seconds=1)
    with pytest.raises(Throttled):
        services.submit(values=inputs(), key="two")


def test_duplicate_verdict_discloses_no_matching_object():
    first = services.submit(values=inputs(), key="first")
    second = services.submit(values=inputs(phone="+255712345679"), key="second")
    assert second.verdicts["duplicates"] == "FOUND"
    assert str(first.property.pk) not in str(services.public_result(second))


def test_postgresql_rejects_direct_history_mutation():
    from django.db import DatabaseError
    check = services.submit(values=inputs(), key="history")
    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("UPDATE free_checks_freecheck SET description='changed' WHERE id=%s", [check.pk])


def test_report_media_cannot_be_repointed_or_deleted():
    from django.db import DatabaseError
    check = services.submit(values=inputs(), key="media-history")
    media_id = check.reports.get().media_id
    for sql in ["UPDATE media_media SET file_key='replacement.pdf' WHERE id=%s", "DELETE FROM media_media WHERE id=%s"]:
        with pytest.raises(DatabaseError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(sql, [media_id])


def test_photo_mismatch_uses_file_provenance():
    from io import BytesIO
    from PIL import Image
    from django.contrib.gis.geos import Point
    from django.core.files.uploadedfile import SimpleUploadedFile
    stream = BytesIO()
    Image.new("RGB", (10, 10)).save(stream, format="PNG")
    image = SimpleUploadedFile("photo.png", stream.getvalue(), content_type="image/png")
    with patch("apps.free_checks.services.image_metadata", return_value=(Point(35, -5, srid=4326), None)):
        check = services.submit(values=inputs(), key="photo", photos=[image])
    assert check.verdicts["photos"] == "MISMATCH"
    assert check.photos.count() == 1


def test_geography_adapter_verdict_is_validated():
    from django.test import override_settings
    with override_settings(FREE_CHECK_GEOGRAPHY_PROVIDER="example.Provider"), patch("apps.free_checks.services.import_string") as provider:
        provider.return_value.return_value.check.return_value = {"land": "LAND", "description_match": "MISMATCH"}
        check = services.submit(values=inputs(), key="geo")
        assert check.verdicts["land"] == "LAND" and check.verdicts["description_match"] == "MISMATCH"
        provider.return_value.return_value.check.return_value = {"land": "invented", "description_match": "MATCH"}
        with pytest.raises(ValidationError):
            services.submit(values=inputs(), key="invalid-provider")


@pytest.mark.django_db(transaction=True)
def test_concurrent_quota_cannot_exceed_limit():
    manager = account("management")
    change_setting(actor=manager, key="free_check_daily_limit", value=1)
    import uuid
    def submit():
        try:
            services.submit(values=inputs(), key=uuid.uuid4().hex)
            return "OK"
        except Throttled:
            return "LIMIT"
    assert sorted(concurrent(submit)) == ["LIMIT", "OK"]
    assert FreeCheck.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_replay_creates_one_report():
    assert len(set(concurrent(lambda: str(services.submit(values=inputs(), key="same").pk)))) == 1
    assert FreeCheck.objects.count() == 1
