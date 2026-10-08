from decimal import Decimal
from io import BytesIO
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point, Polygon
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.media.models import Media
from apps.properties.models import PropertyRecord
from apps.roles.catalog import ROLE_MANAGEMENT, ROLE_OWNER, ROLE_VERIFIER
from apps.roles.models import Role, UserRole
from apps.roles.services import bootstrap_canonical_roles
from apps.localities.models import District, Locality, Region, Ward
from apps.site_capture.audit_events import SITE_CAPTURE_CREATED, SITE_CAPTURE_PROMOTED, SITE_CAPTURE_SUBMITTED, SITE_CAPTURE_UPDATED
from apps.site_capture.models import SiteCapture
from apps.site_capture.services import create_site_capture, submit_site_capture
from apps.verification.services import get_effective_verification_level


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


def point_payload(longitude=39.25, latitude=-6.79):
    return {"type": "Point", "coordinates": [longitude, latitude]}


def boundary_payload():
    return {
        "type": "Polygon",
        "coordinates": [[[39.24, -6.80], [39.26, -6.80], [39.26, -6.78], [39.24, -6.80]]],
    }


def create_user(email=None):
    email = email or f"capture-api-{uuid.uuid4().hex[:10]}@example.test"
    return get_user_model().objects.create_user(
        email=email,
        phone=f"+2557{abs(hash(email)) % 100000000:08d}",
        full_name="Site Capture API User",
        password="StrongPass123!",
    )


def grant_role(user, role_code):
    bootstrap_canonical_roles()
    return UserRole.objects.create(user=user, role=Role.objects.get(code=role_code))


def client_for(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user=user)
    return client


def property_record(owner, prefix=None):
    prefix = prefix or f"CaptureApi{uuid.uuid4().hex[:8]}"
    region = Region.objects.create(name=f"{prefix} Region")
    district = District.objects.create(region=region, name=f"{prefix} District")
    ward = Ward.objects.create(district=district, name=f"{prefix} Ward")
    locality = Locality.objects.create(ward=ward, name=f"{prefix} Street", kind=Locality.Kind.STREET, approved=True)
    return PropertyRecord.objects.create(
        property_id=f"OWR-{uuid.uuid4().hex[:16].upper()}",
        category=PropertyRecord.Category.LAND,
        pin=Point(39.2083, -6.7924, srid=4326),
        boundary=None,
        region=region,
        district=district,
        ward=ward,
        locality=locality,
        stated_size=Decimal("1200.50"),
        size_unit="sqm",
        title_type=PropertyRecord.TitleType.UNKNOWN,
        created_by=owner,
    )


def owner_and_property(prefix="CaptureApi"):
    owner = create_user(f"{prefix.lower()}@example.test")
    grant_role(owner, ROLE_OWNER)
    return owner, property_record(owner, prefix)


def create_capture(owner, property_record_instance, *, boundary=None, submitted=False):
    capture = create_site_capture(
        property_record=property_record_instance,
        actor=owner,
        observed_point=Point(39.25, -6.79, srid=4326),
        observed_boundary=boundary if boundary is not None else Polygon(((39.25, -6.79), (39.251, -6.79), (39.251, -6.789), (39.25, -6.79)), srid=4326),
    )
    return submit_site_capture(site_capture=capture, actor=owner) if submitted else capture


def image_upload():
    image = Image.new("RGB", (32, 24), color=(90, 120, 150))
    output = BytesIO()
    image.save(output, format="JPEG")
    return SimpleUploadedFile("capture.jpg", output.getvalue(), content_type="image/jpeg")


def test_create_api_enforces_authority_geometry_and_safe_server_fields():
    owner, property_record_instance = owner_and_property("Create")
    url = f"/api/v1/properties/{property_record_instance.property_id}/site-captures/"
    payload = {"observed_point": point_payload(), "observed_boundary": boundary_payload()}

    response = client_for(owner).post(url, payload, format="json")

    assert response.status_code == 201
    assert response.data["capture_id"].startswith("CAP-")
    assert response.data["property_id"] == property_record_instance.property_id
    assert response.data["status"] == SiteCapture.Status.DRAFT
    assert response.data["observed_point"] == point_payload()
    assert response.data["observed_boundary"] == boundary_payload()
    assert {"captured_by", "id", "email", "phone", "device", "file_key", "file_hash"}.isdisjoint(response.data)
    assert AuditLog.objects.filter(action=SITE_CAPTURE_CREATED).count() == 1

    management = create_user("capture-api-management@example.test")
    grant_role(management, ROLE_MANAGEMENT)
    assert client_for(management).post(url, {"observed_point": point_payload(39.26, -6.78)}, format="json").status_code == 201

    unrelated = create_user("capture-api-unrelated@example.test")
    assert client_for(unrelated).post(url, payload, format="json").status_code == 403
    assert client_for().post(url, payload, format="json").status_code == 401
    assert client_for(owner).post(url, {**payload, "status": "SUBMITTED"}, format="json").status_code == 400
    assert client_for(owner).post(url, {"observed_point": point_payload(181, 0)}, format="json").status_code == 400


def test_list_and_detail_are_private_scoped_paginated_and_deterministic():
    owner, first_property = owner_and_property("ListFirst")
    second_property = property_record(owner, "ListSecond")
    first = create_capture(owner, first_property)
    second = create_capture(owner, first_property)
    create_capture(owner, second_property)
    first_url = f"/api/v1/properties/{first_property.property_id}/site-captures/?page_size=1"

    response = client_for(owner).get(first_url)

    assert response.status_code == 200
    assert response.data["count"] == 2
    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["capture_id"] == second.capture_id
    assert client_for().get(first_url).status_code == 401
    unrelated = create_user("capture-api-list-unrelated@example.test")
    assert client_for(unrelated).get(first_url).status_code == 403

    detail_url = f"/api/v1/site-captures/{first.capture_id}/"
    assert client_for(owner).get(detail_url).status_code == 200
    assert client_for(unrelated).get(detail_url).status_code == 403
    assert client_for().get(detail_url).status_code == 401
    assert client_for(owner).get("/api/v1/site-captures/CAP-0000000000000000/").status_code == 404


def test_patch_api_allows_only_draft_geometry_and_preserves_property():
    owner, property_record_instance = owner_and_property("Patch")
    capture = create_capture(owner, property_record_instance, boundary=Polygon(((39.24, -6.80), (39.26, -6.80), (39.26, -6.78), (39.24, -6.80)), srid=4326))
    original_property_pin = property_record_instance.pin.clone()
    url = f"/api/v1/site-captures/{capture.capture_id}/"

    point_response = client_for(owner).patch(url, {"observed_point": point_payload(39.27, -6.77)}, format="json")
    boundary_response = client_for(owner).patch(url, {"observed_boundary": None}, format="json")

    assert point_response.status_code == 200
    assert boundary_response.status_code == 200
    capture.refresh_from_db()
    property_record_instance.refresh_from_db()
    assert capture.observed_boundary is None
    assert property_record_instance.pin.equals_exact(original_property_pin, tolerance=0)
    assert AuditLog.objects.filter(action=SITE_CAPTURE_UPDATED).count() == 2
    assert client_for(owner).patch(url, {"capture_id": "CAP-OVERRIDE"}, format="json").status_code == 400
    assert client_for(owner).patch(url, {"verification_level": 3}, format="json").status_code == 400
    assert client_for(owner).patch(url, {"observed_point": point_payload(181, 0)}, format="json").status_code == 400
    assert client_for(owner).put(url, {"observed_point": point_payload()}, format="json").status_code == 405


def test_submit_and_promotion_apis_are_allowlisted_and_service_owned():
    owner, property_record_instance = owner_and_property("SubmitPromote")
    capture = create_capture(owner, property_record_instance, boundary=Polygon(((39.24, -6.80), (39.26, -6.80), (39.26, -6.78), (39.24, -6.80)), srid=4326))
    submit_url = f"/api/v1/site-captures/{capture.capture_id}/submit/"
    promote_url = f"/api/v1/site-captures/{capture.capture_id}/promote/"
    initial_level = get_effective_verification_level(user=owner, property_record=property_record_instance)

    assert client_for(owner).post(submit_url, {"status": "SUBMITTED"}, format="json").status_code == 400
    assert client_for(owner).post(submit_url, {}, format="json").status_code == 200
    assert client_for(owner).post(submit_url, {}, format="json").status_code == 400
    assert client_for(owner).patch(f"/api/v1/site-captures/{capture.capture_id}/", {"observed_point": point_payload()}, format="json").status_code == 400

    assert client_for(owner).post(promote_url, {"promote_point": "true"}, format="json").status_code == 400
    assert client_for(owner).post(promote_url, {"promote_point": 1}, format="json").status_code == 400
    assert client_for(owner).post(promote_url, {"promote_point": None}, format="json").status_code == 400
    assert client_for(owner).post(promote_url, {"pin": point_payload()}, format="json").status_code == 400
    response = client_for(owner).post(promote_url, {"promote_point": True, "promote_boundary": True}, format="json")
    assert response.status_code == 200
    property_record_instance.refresh_from_db()
    assert property_record_instance.pin.equals_exact(capture.observed_point, tolerance=0)
    assert property_record_instance.boundary.equals_exact(capture.observed_boundary, tolerance=0)
    assert get_effective_verification_level(user=owner, property_record=property_record_instance) == initial_level
    assert AuditLog.objects.filter(action=SITE_CAPTURE_SUBMITTED).count() == 1
    assert AuditLog.objects.filter(action=SITE_CAPTURE_PROMOTED).count() == 1


def test_capture_api_authorization_uses_persisted_property_policy_only():
    owner, property_record_instance = owner_and_property("Authorization")
    capture = create_capture(owner, property_record_instance)
    for actor, role in ((create_user("capture-api-verifier@example.test"), ROLE_VERIFIER), (create_user("capture-api-owner@example.test"), ROLE_OWNER)):
        grant_role(actor, role)
        actor.is_staff = True
        actor.is_superuser = True
        actor.role = ROLE_MANAGEMENT
        actor.save(update_fields=["is_staff", "is_superuser"])
        assert client_for(actor).get(f"/api/v1/site-captures/{capture.capture_id}/").status_code == 403
        assert client_for(actor).post(f"/api/v1/site-captures/{capture.capture_id}/submit/", {}, format="json").status_code == 403


def test_capture_media_routes_use_existing_media_services_and_safe_serialization():
    owner, property_record_instance = owner_and_property("Media")
    capture = create_capture(owner, property_record_instance)
    upload_url = f"/api/v1/site-captures/{capture.capture_id}/media/"

    assert client_for(owner).post(
        upload_url,
        {"image": image_upload(), "source": "SITE_CAPTURE"},
        format="multipart",
    ).status_code == 400
    assert client_for(owner).post(
        upload_url,
        {"image": image_upload(), "owner": str(capture.pk)},
        format="multipart",
    ).status_code == 400
    upload_response = client_for(owner).post(upload_url, {"image": image_upload()}, format="multipart")

    assert upload_response.status_code == 201
    assert {"file_key", "file_hash", "captured_location", "device", "url"}.isdisjoint(upload_response.data)
    media = Media.objects.get(media_id=upload_response.data["media_id"])
    assert media.owner == capture
    remove_url = f"/api/v1/site-captures/{capture.capture_id}/media/{media.media_id}/"
    second_capture = create_capture(owner, property_record_instance)
    assert client_for(owner).delete(
        f"/api/v1/site-captures/{second_capture.capture_id}/media/{media.media_id}/"
    ).status_code == 404
    assert client_for(owner).delete(remove_url).status_code == 204
    assert not Media.objects.filter(pk=media.pk).exists()
    submit_site_capture(site_capture=capture, actor=owner)
    assert client_for(owner).post(upload_url, {"image": image_upload()}, format="multipart").status_code == 400


def test_private_capture_actions_reject_mass_assignment_and_cross_object_identifiers():
    owner, first_property = owner_and_property("HardeningFirst")
    second_property = property_record(owner, "HardeningSecond")
    first_capture = create_capture(owner, first_property)
    second_capture = create_capture(owner, second_property)
    collection_url = f"/api/v1/properties/{first_property.property_id}/site-captures/"
    detail_url = f"/api/v1/site-captures/{first_capture.capture_id}/"
    submit_url = f"/api/v1/site-captures/{first_capture.capture_id}/submit/"

    create_payload = {
        "observed_point": point_payload(),
        "capture_id": second_capture.capture_id,
        "property": str(second_property.pk),
        "property_id": second_property.property_id,
        "captured_by": str(owner.pk),
        "captured_at": "2020-01-01T00:00:00Z",
        "status": SiteCapture.Status.SUBMITTED,
        "created_at": "2020-01-01T00:00:00Z",
        "updated_at": "2020-01-01T00:00:00Z",
        "verification_level": 3,
        "reviewer": str(owner.pk),
        "role": ROLE_MANAGEMENT,
        "source": "SITE_CAPTURE",
        "media": ["anything"],
        "device": "untrusted-device",
        "captured_location": point_payload(),
    }
    assert client_for(owner).post(collection_url, create_payload, format="json").status_code == 400
    assert SiteCapture.objects.filter(property=first_property).count() == 1

    patch_payload = {
        "capture_id": second_capture.capture_id,
        "property": str(second_property.pk),
        "property_id": second_property.property_id,
        "captured_by": str(owner.pk),
        "captured_at": "2020-01-01T00:00:00Z",
        "status": SiteCapture.Status.SUBMITTED,
        "created_at": "2020-01-01T00:00:00Z",
        "updated_at": "2020-01-01T00:00:00Z",
        "verification_level": 3,
        "reviewer": str(owner.pk),
        "role": ROLE_MANAGEMENT,
        "media": ["anything"],
        "media_id": "MED-OVERRIDE",
        "source": "SITE_CAPTURE",
    }
    assert client_for(owner).patch(detail_url, patch_payload, format="json").status_code == 400
    assert client_for(owner).post(submit_url, {"property": str(second_property.pk)}, format="json").status_code == 400

    nested_second_url = f"/api/v1/properties/{second_property.property_id}/site-captures/"
    response = client_for(owner).get(nested_second_url)
    assert response.status_code == 200
    assert [item["capture_id"] for item in response.data["results"]] == [second_capture.capture_id]


def test_media_delete_requires_an_empty_action_body():
    owner, property_record_instance = owner_and_property("DeletePayload")
    capture = create_capture(owner, property_record_instance)
    upload_url = f"/api/v1/site-captures/{capture.capture_id}/media/"
    media = Media.objects.get(media_id=client_for(owner).post(upload_url, {"image": image_upload()}, format="multipart").data["media_id"])
    remove_url = f"/api/v1/site-captures/{capture.capture_id}/media/{media.media_id}/"

    response = client_for(owner).delete(remove_url, {"capture_id": "CAP-OVERRIDE"}, format="json")

    assert response.status_code == 400
    assert Media.objects.filter(pk=media.pk).exists()
