import pytest
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.listings.tests.test_services import create_user, create_listing_for
from apps.listings.tests.test_api import client_for
from apps.roles.legacy_authorization.models import Role, UserRole, Permission, RolePermission
from apps.audit.models import AuditLog
from apps.leads.models import Lead
from apps.leads.services import create_lead, LeadTransitionService, add_note, set_follow_up

pytestmark = pytest.mark.django_db


def grant(user, code):
    # TransactionTestCase flush removes migration seeds between concurrency tests.
    from apps.roles.legacy_authorization.catalog import DEFAULT_ROLE_PERMISSIONS, CATALOG
    role, _ = Role.objects.get_or_create(code=code, defaults={"name": code})
    for permission_code in DEFAULT_ROLE_PERMISSIONS[code]:
        permission, _ = Permission.objects.get_or_create(code=permission_code, defaults={"name": CATALOG[permission_code][0]})
        RolePermission.objects.get_or_create(role=role, permission=permission)
    return UserRole.objects.create(user=user, role=role)


@pytest.fixture
def pipeline():
    buyer, lister = create_user(), create_user()
    grant(buyer, "buyer")
    grant(lister, "agent")
    listing = create_listing_for(lister, lister_kind="AGENT", status="ACTIVE")
    lead = create_lead(actor=buyer, listing_id=listing.listing_id, source="ENQUIRY")
    return buyer, lister, listing, lead


@pytest.mark.parametrize("source", Lead.Source.values)
def test_interest_sources(pipeline, source):
    buyer, lister, listing, _ = pipeline
    lead = create_lead(actor=buyer, listing_id=listing.listing_id, source=source)
    assert lead.stage == "NEW" and lead.buyer_whatsapp == buyer.phone
    assert lead.property_id == listing.property_id and lead.lister_id == lister.pk


def test_pipeline_history_notes_followup(pipeline):
    _, lister, _, lead = pipeline
    for stage in ["CONTACTED", "VIEWING", "NEGOTIATION"]:
        LeadTransitionService.transition(actor=lister, lead_id=lead.pk, stage=stage)
    assert lead.transitions.count() == 3
    add_note(actor=lister, lead_id=lead.pk, text="Private customer note")
    set_follow_up(actor=lister, lead_id=lead.pk, follow_up_at=timezone.now())
    assert lead.notes.count() == 1
    assert len(client_for(lister).get('/api/v1/leads/customers/').data) == 1


@pytest.mark.parametrize("stage", ["WON", "VIEWING"])
def test_forbidden_transition(pipeline, stage):
    _, lister, _, lead = pipeline
    with pytest.raises(ValidationError):
        LeadTransitionService.transition(actor=lister, lead_id=lead.pk, stage=stage)


def test_lost_reason_and_terminal(pipeline):
    _, lister, _, lead = pipeline
    with pytest.raises(ValidationError):
        LeadTransitionService.transition(actor=lister, lead_id=lead.pk, stage="LOST")
    LeadTransitionService.transition(actor=lister, lead_id=lead.pk, stage="LOST", reason="Buyer withdrew")
    lead.refresh_from_db()
    assert lead.lost_at and lead.stage == "LOST"
    assert AuditLog.objects.filter(action="lead.lost", entity_id=str(lead.pk)).count() == 1


def test_object_scope_and_revocation(pipeline):
    buyer, lister, _, lead = pipeline
    stranger = create_user()
    grant(stranger, "agent")
    assert client_for(stranger).get(f'/api/v1/leads/{lead.pk}/').status_code == 404
    assert client_for(buyer).get(f'/api/v1/leads/{lead.pk}/').status_code == 403
    with pytest.raises(PermissionDenied):
        add_note(actor=stranger, lead_id=lead.pk, text="No")
    UserRole.objects.filter(user=lister).update(is_active=False)
    with pytest.raises(PermissionDenied):
        add_note(actor=lister, lead_id=lead.pk, text="No")


def test_transition_audit_failure_rolls_back(pipeline, monkeypatch):
    _, lister, _, lead = pipeline
    def fail(*args, **kwargs):
        raise RuntimeError("audit unavailable")
    monkeypatch.setattr('apps.leads.services.audit', fail)
    with pytest.raises(RuntimeError):
        LeadTransitionService.transition(actor=lister, lead_id=lead.pk, stage="CONTACTED")
    lead.refresh_from_db()
    assert lead.stage == "NEW" and lead.transitions.count() == 0


def test_customer_list_shows_each_enquiry_with_property_and_newest_note_first(pipeline):
    """LEAD-02, LEAD-06: the lister's private customer page."""
    buyer, lister, listing, lead = pipeline
    add_note(actor=lister, lead_id=lead.pk, text="First call")
    add_note(actor=lister, lead_id=lead.pk, text="Viewing on Saturday")
    customer = client_for(lister).get("/api/v1/leads/customers/").data[0]
    row = customer["leads"][0]
    assert customer["whatsapp"] == buyer.phone and row["listing_id"] == listing.listing_id and row["source"] == "ENQUIRY"
    assert [note["text"] for note in row["notes"]] == ["Viewing on Saturday", "First call"]


def test_buyer_sees_own_enquiries_without_the_listers_stage(pipeline):
    """SRD 24."""
    buyer, lister, listing, lead = pipeline
    rows = client_for(buyer).get("/api/v1/leads/mine/").data
    assert [row["id"] for row in rows] == [str(lead.pk)] and "stage" not in rows[0] and rows[0]["deal_id"] is None
    assert client_for(lister).get("/api/v1/leads/mine/").data == []
