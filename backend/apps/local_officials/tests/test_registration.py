from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from apps.local_officials.full_check import eligible_officials
from apps.local_officials.models import LocalOfficialProfile
from apps.verification.tests.test_field_lifecycle import submitted_field
from .test_full_check_coverage import official_with_assignment

pytestmark = pytest.mark.django_db


def png(name):
    buffer = BytesIO()
    Image.new("RGB", (8, 8), (200, 145, 40)).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def form(email):
    return {"full_name": "Asha Mussa", "position": "MWENYEKITI", "national_id_number": "19800101-12345-00001-1", "email": email, "password": "Mtaa-wa-Mbezi-2026!", "photo": png("me.png"), "stamp_photo": png("stamp.png")}


def setup():
    _, property_record, _, _ = submitted_field()
    _, manager, _, _ = official_with_assignment(property_record)
    property_record.locality.approved = True
    property_record.locality.save(update_fields=["approved"])
    staff = APIClient()
    staff.force_authenticate(manager)
    return property_record, staff


def invite(staff, locality, phone="+255713000111"):
    response = staff.post("/api/v1/management/local-officials/invites/", {"locality": str(locality.pk), "phone": phone}, format="json")
    assert response.status_code == 201, response.data
    link = response.data["delivery"]["link"]
    assert response.data["delivery"]["whatsapp_link"].startswith("https://wa.me/255713000111")
    return link.rsplit("/", 1)[-1]


def test_invited_official_registers_once_and_is_routed_after_approval():
    property_record, staff = setup()
    token = invite(staff, property_record.locality)
    public = APIClient()
    shown = public.get(f"/api/v1/local-official/register/{token}/")
    assert shown.status_code == 200 and shown.data["locality"]["name"] == property_record.locality.name
    assert shown.data["phone"].endswith("0111") and "+255" not in shown.data["phone"]

    created = public.post(f"/api/v1/local-official/register/{token}/", form("asha@example.test"), format="multipart")
    assert created.status_code == 201, created.data
    profile = LocalOfficialProfile.objects.get(official_id=created.data["official_id"])
    assert profile.status == "AWAITING_APPROVAL" and not profile.user.is_active and profile.user.phone == "+255713000111"
    assert profile.photo and profile.stamp_photo
    assert public.post(f"/api/v1/local-official/register/{token}/", form("other@example.test"), format="multipart").status_code == 404

    approved = staff.post(f"/api/v1/management/local-officials/{profile.official_id}/approve/")
    assert approved.status_code == 200, approved.data
    assert approved.data["status"] == "ACTIVE" and approved.data["documents"] == {"received": 3, "total": 3}
    profile.refresh_from_db()
    assert profile.user.is_active and profile.user.has_role("local_official")
    assert profile.pk in {item.pk for item in eligible_officials(property_record)}


def test_deactivation_stops_routing_and_replacement_reuses_the_office_number():
    property_record, staff = setup()
    token = invite(staff, property_record.locality)
    created = APIClient().post(f"/api/v1/local-official/register/{token}/", form("asha@example.test"), format="multipart")
    official_id = created.data["official_id"]
    staff.post(f"/api/v1/management/local-officials/{official_id}/approve/")

    assert staff.post(f"/api/v1/management/local-officials/{official_id}/deactivate/", {}, format="json").status_code == 400
    response = staff.post(f"/api/v1/management/local-officials/{official_id}/deactivate/", {"reason": "Left office", "replacement_phone": "0713000111"}, format="json")
    assert response.status_code == 200, response.data
    assert response.data["official"]["status"] == "DEACTIVATED"
    assert response.data["invite"]["replaces"]["official_id"] == official_id
    old = LocalOfficialProfile.objects.get(official_id=official_id)
    assert not old.user.is_active and eligible_officials(property_record) == []

    token = response.data["invite"]["delivery"]["link"].rsplit("/", 1)[-1]
    again = APIClient().post(f"/api/v1/local-official/register/{token}/", form("juma@example.test"), format="multipart")
    assert again.status_code == 201, again.data
    old.user.refresh_from_db()
    assert old.user.phone != "+255713000111"
    assert LocalOfficialProfile.objects.get(official_id=again.data["official_id"]).user.phone == "+255713000111"


def test_number_of_an_active_account_cannot_be_invited_and_coverage_counts_officials():
    property_record, staff = setup()
    holder = property_record.created_by
    response = staff.post("/api/v1/management/local-officials/invites/", {"locality": str(property_record.locality.pk), "phone": holder.phone}, format="json")
    assert response.status_code == 400
    coverage = staff.get("/api/v1/management/local-officials/coverage/")
    assert coverage.status_code == 200 and coverage.data["level"] == "region"
    region = next(row for row in coverage.data["rows"] if row["id"] == str(property_record.region_id))
    assert region["localities"] >= 1 and region["covered"] == 0
    wards = staff.get(f"/api/v1/management/local-officials/coverage/?district={property_record.district_id}")
    assert wards.data["level"] == "ward" and [crumb["id"] for crumb in wards.data["crumbs"]] == [str(property_record.region_id), str(property_record.district_id)]
