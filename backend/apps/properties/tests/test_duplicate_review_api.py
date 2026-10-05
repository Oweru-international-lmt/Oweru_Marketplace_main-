from decimal import Decimal
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.listings.models import Listing
from apps.localities.models import District, Locality, Region, Ward
from apps.properties.audit_events import PROPERTY_DUPLICATE_CONFIRMED, PROPERTY_DUPLICATE_DISMISSED
from apps.properties.duplicate_services import record_possible_duplicate
from apps.properties.models import PossibleDuplicate, PropertyRecord
from apps.roles.catalog import ROLE_AGENT, ROLE_BUYER, ROLE_MANAGEMENT, ROLE_OWNER, ROLE_VERIFIER
from apps.roles.models import Role, UserRole
from apps.roles.services import bootstrap_canonical_roles


pytestmark = pytest.mark.django_db


def create_user(role_code=None, *, email=None, is_active=True, role_active=True, assignment_active=True):
    email = email or f"duplicate-review-{uuid.uuid4().hex[:10]}@example.test"
    user = get_user_model().objects.create_user(
        email=email,
        phone=f"+2557{abs(hash(email)) % 100000000:08d}",
        full_name="Duplicate Reviewer",
        password="StrongPass123!",
        is_active=is_active,
    )
    if role_code:
        bootstrap_canonical_roles()
        role = Role.objects.get(code=role_code)
        role.is_active = role_active
        role.save(update_fields=["is_active"])
        UserRole.objects.create(user=user, role=role, assigned_by=user, is_active=assignment_active)
    return user


def client_for(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user=user)
    return client


def hierarchy(prefix):
    region = Region.objects.create(name=f"{prefix} Region")
    district = District.objects.create(region=region, name=f"{prefix} District")
    ward = Ward.objects.create(district=district, name=f"{prefix} Ward")
    locality = Locality.objects.create(ward=ward, name=f"{prefix} Street", kind=Locality.Kind.STREET, approved=True)
    return region, district, ward, locality


def property_record(prefix, *, owner=None, stated_size=Decimal("1200.00"), longitude=39.2083):
    owner = owner or create_user(email=f"{prefix.lower()}-owner@example.test")
    region, district, ward, locality = hierarchy(prefix)
    return PropertyRecord.objects.create(
        property_id=f"OWR-{uuid.uuid4().hex[:16].upper()}",
        category=PropertyRecord.Category.LAND,
        pin=Point(longitude, -6.7924, srid=4326),
        boundary=None,
        region=region,
        district=district,
        ward=ward,
        locality=locality,
        stated_size=stated_size,
        size_unit="sqm",
        title_type=PropertyRecord.TitleType.UNKNOWN,
        created_by=owner,
    )


def listing_for(owner, prop):
    return Listing.objects.create(
        listing_id=f"LST-{uuid.uuid4().hex[:16].upper()}",
        property=prop,
        lister=owner,
        lister_kind=Listing.ListerKind.OWNER,
        selling_price=Decimal("100000000"),
        owner_price=Decimal("100000000"),
        currency=Listing.Currency.TZS,
        status=Listing.Status.DRAFT,
        description="Review safety listing.",
        features=[],
    )


def duplicate_candidate(prefix="Candidate", *, signal=None):
    first = property_record(f"{prefix}A", longitude=39.2083)
    second = property_record(f"{prefix}B", longitude=39.2084)
    return record_possible_duplicate(
        property_a=first,
        property_b=second,
        signals=[signal or PossibleDuplicate.SIGNAL_PIN_PROXIMITY],
        distance_meters=Decimal("12.34"),
        size_difference_percent=Decimal("5.00"),
    )


def list_url(query=""):
    return f"/api/v1/management/property-duplicates/{query}"


def detail_url(candidate):
    return f"/api/v1/management/property-duplicates/{candidate.pk}/"


def confirm_url(candidate):
    return f"/api/v1/management/property-duplicates/{candidate.pk}/confirm/"


def dismiss_url(candidate):
    return f"/api/v1/management/property-duplicates/{candidate.pk}/dismiss/"


def response_text(response):
    return str(getattr(response, "data", "")) + getattr(response, "content", b"").decode(errors="ignore")


def test_management_can_list_pending_and_filter_statuses():
    manager = create_user(ROLE_MANAGEMENT, email="duplicate-queue-manager@example.test")
    pending = duplicate_candidate("QueuePending")
    confirmed = duplicate_candidate("QueueConfirmed")
    dismissed = duplicate_candidate("QueueDismissed")
    client = client_for(manager)

    assert client.post(confirm_url(confirmed), {}, format="json").status_code == 200
    assert client.post(dismiss_url(dismissed), {}, format="json").status_code == 200

    default_ids = {item["id"] for item in client.get(list_url()).data}
    confirmed_ids = {item["id"] for item in client.get(list_url("?status=CONFIRMED_DUPLICATE")).data}
    dismissed_ids = {item["id"] for item in client.get(list_url("?status=NOT_DUPLICATE")).data}
    pending_ids = {item["id"] for item in client.get(list_url("?status=PENDING")).data}

    assert default_ids == {str(pending.pk)}
    assert pending_ids == {str(pending.pk)}
    assert confirmed_ids == {str(confirmed.pk)}
    assert dismissed_ids == {str(dismissed.pk)}


def test_management_detail_response_uses_safe_duplicate_serializer():
    owner = create_user(ROLE_OWNER, email="duplicate-private-owner@example.test")
    first = property_record("DetailSafeA", owner=owner)
    second = property_record("DetailSafeB")
    candidate = record_possible_duplicate(
        property_a=first,
        property_b=second,
        signals=[PossibleDuplicate.SIGNAL_PIN_PROXIMITY, PossibleDuplicate.SIGNAL_SIZE_SIMILARITY],
        distance_meters=Decimal("12.34"),
        size_difference_percent=Decimal("5.00"),
    )

    response = client_for(create_user(ROLE_MANAGEMENT)).get(detail_url(candidate))

    assert response.status_code == 200
    assert response.data["id"] == str(candidate.pk)
    assert response.data["status"] == PossibleDuplicate.Status.PENDING
    assert response.data["property_a"]["property_id"] in {first.property_id, second.property_id}
    combined = response_text(response).lower()
    assert "coordinates" not in combined
    assert "boundary" not in combined
    assert "file_hash" not in combined
    assert "storage" not in combined
    assert "signed" not in combined
    assert owner.email not in combined
    assert owner.phone not in combined
    assert "identity" not in combined
    assert "bank" not in combined


@pytest.mark.parametrize("role_code", [ROLE_OWNER, ROLE_AGENT, ROLE_BUYER, ROLE_VERIFIER])
def test_non_management_roles_are_denied(role_code):
    candidate = duplicate_candidate(f"Deny{role_code}")
    user = create_user(role_code)
    client = client_for(user)

    assert client.get(list_url()).status_code == 403
    assert client.get(detail_url(candidate)).status_code == 403
    assert client.post(confirm_url(candidate), {}, format="json").status_code == 403
    assert client.post(dismiss_url(candidate), {}, format="json").status_code == 403


def test_anonymous_inactive_revoked_inactive_role_and_fake_management_are_denied():
    candidate = duplicate_candidate("DenyManagementState")
    inactive = create_user(ROLE_MANAGEMENT, is_active=False)
    revoked = create_user(ROLE_MANAGEMENT, assignment_active=False)
    inactive_role = create_user(ROLE_MANAGEMENT, role_active=False)
    fake = create_user(ROLE_BUYER)
    fake.role = ROLE_MANAGEMENT
    fake.roles = [ROLE_MANAGEMENT]
    fake.jwt = {"roles": [ROLE_MANAGEMENT]}

    assert client_for().get(list_url()).status_code == 401
    for user in [inactive, revoked, inactive_role, fake]:
        assert client_for(user).get(detail_url(candidate)).status_code == 403
        assert client_for(user).post(confirm_url(candidate), {}, format="json").status_code == 403


def test_confirm_pending_sets_reviewer_audits_once_and_does_not_mutate_property_or_listing():
    manager = create_user(ROLE_MANAGEMENT, email="duplicate-confirm-manager@example.test")
    owner = create_user(ROLE_OWNER, email="duplicate-confirm-owner@example.test")
    first = property_record("ConfirmSafeA", owner=owner)
    second = property_record("ConfirmSafeB")
    listing = listing_for(owner, first)
    candidate = record_possible_duplicate(property_a=first, property_b=second, signals=[PossibleDuplicate.SIGNAL_PIN_PROXIMITY])
    before = (first.property_id, second.property_id, listing.status, Listing.objects.count(), PropertyRecord.objects.count())

    response = client_for(manager).post(confirm_url(candidate), {}, format="json")

    candidate.refresh_from_db()
    first.refresh_from_db()
    second.refresh_from_db()
    listing.refresh_from_db()
    assert response.status_code == 200
    assert candidate.status == PossibleDuplicate.Status.CONFIRMED_DUPLICATE
    assert candidate.reviewed_by == manager
    assert candidate.reviewed_at is not None
    assert (first.property_id, second.property_id, listing.status, Listing.objects.count(), PropertyRecord.objects.count()) == before
    assert AuditLog.objects.filter(action=PROPERTY_DUPLICATE_CONFIRMED, entity_id=str(candidate.pk)).count() == 1


def test_dismiss_pending_sets_reviewer_and_audits_once():
    manager = create_user(ROLE_MANAGEMENT, email="duplicate-dismiss-manager@example.test")
    candidate = duplicate_candidate("DismissAPI")

    response = client_for(manager).post(dismiss_url(candidate), {}, format="json")

    candidate.refresh_from_db()
    assert response.status_code == 200
    assert candidate.status == PossibleDuplicate.Status.NOT_DUPLICATE
    assert candidate.reviewed_by == manager
    assert candidate.reviewed_at is not None
    assert AuditLog.objects.filter(action=PROPERTY_DUPLICATE_DISMISSED, entity_id=str(candidate.pk)).count() == 1


def test_reviewed_candidates_fail_closed_without_success_audit():
    manager = create_user(ROLE_MANAGEMENT, email="duplicate-repeat-manager@example.test")
    confirmed = duplicate_candidate("RepeatConfirmed")
    dismissed = duplicate_candidate("RepeatDismissed")
    client = client_for(manager)

    assert client.post(confirm_url(confirmed), {}, format="json").status_code == 200
    assert client.post(dismiss_url(dismissed), {}, format="json").status_code == 200
    before_confirm_audits = AuditLog.objects.filter(action=PROPERTY_DUPLICATE_CONFIRMED).count()
    before_dismiss_audits = AuditLog.objects.filter(action=PROPERTY_DUPLICATE_DISMISSED).count()

    assert client.post(confirm_url(confirmed), {}, format="json").status_code == 400
    assert client.post(dismiss_url(confirmed), {}, format="json").status_code == 400
    assert client.post(confirm_url(dismissed), {}, format="json").status_code == 400
    assert client.post(dismiss_url(dismissed), {}, format="json").status_code == 400
    assert AuditLog.objects.filter(action=PROPERTY_DUPLICATE_CONFIRMED).count() == before_confirm_audits
    assert AuditLog.objects.filter(action=PROPERTY_DUPLICATE_DISMISSED).count() == before_dismiss_audits


def test_unknown_invalid_filter_and_unsupported_methods_use_safe_http_errors():
    manager = create_user(ROLE_MANAGEMENT, email="duplicate-errors-manager@example.test")
    candidate = duplicate_candidate("Errors")
    client = client_for(manager)

    assert client.get(f"/api/v1/management/property-duplicates/{uuid.uuid4()}/").status_code == 404
    assert client.get(list_url("?status=UNKNOWN")).status_code == 400
    assert client.put(detail_url(candidate), {}, format="json").status_code == 405
    assert client.delete(detail_url(candidate)).status_code == 405
    assert client.get(confirm_url(candidate)).status_code == 405
    assert client.get(dismiss_url(candidate)).status_code == 405
    assert client.put(confirm_url(candidate), {}, format="json").status_code == 405
    assert client.delete(confirm_url(candidate)).status_code == 405


@pytest.mark.parametrize(
    "field",
    [
        "status",
        "signals",
        "property_a",
        "property_b",
        "reviewed_by",
        "reviewed_at",
        "coordinates",
        "hash",
        "owner",
        "listing",
        "media",
        "created_at",
    ],
)
def test_action_endpoints_reject_mass_assignment_fields(field):
    manager = create_user(ROLE_MANAGEMENT)
    candidate = duplicate_candidate(f"MassAssign{field}")

    response = client_for(manager).post(confirm_url(candidate), {field: "hostile"}, format="json")

    candidate.refresh_from_db()
    assert response.status_code == 400
    assert candidate.status == PossibleDuplicate.Status.PENDING
    assert candidate.reviewed_by is None


def test_later_duplicate_detection_preserves_reviewed_decision():
    manager = create_user(ROLE_MANAGEMENT)
    candidate = duplicate_candidate("PreserveAPI")
    assert client_for(manager).post(dismiss_url(candidate), {}, format="json").status_code == 200

    updated = record_possible_duplicate(
        property_a=candidate.property_b,
        property_b=candidate.property_a,
        signals=[PossibleDuplicate.SIGNAL_PHOTO_SIMILARITY],
    )

    assert updated.pk == candidate.pk
    assert updated.status == PossibleDuplicate.Status.NOT_DUPLICATE
    assert PossibleDuplicate.SIGNAL_PHOTO_SIMILARITY in updated.signals


def test_no_public_duplicate_review_endpoint_exists():
    owner = create_user(ROLE_OWNER, email="duplicate-public-owner@example.test")
    client = client_for(owner)

    assert client.get("/api/v1/property-duplicates/").status_code == 404
    assert client.get("/api/v1/properties/duplicates/").status_code == 404
