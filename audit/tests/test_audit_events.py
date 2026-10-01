import pytest
from django.db.models.deletion import ProtectedError
from rest_framework.test import APIClient, APIRequestFactory

from accounts.models import User
from audit.models import AuditEvent
from audit.services import record_event
from authorization.services import record_sensitive_access
from authorization.models import Role


pytestmark = pytest.mark.django_db


def test_event_records_actor_request_metadata_and_states():
    actor = User.objects.create_user(phone="+255700123456", full_name="Asha", password="Strong-pass-482!")
    request = APIRequestFactory().get("/api/v1/", REMOTE_ADDR="203.0.113.10", HTTP_USER_AGENT="OweruTest/1.0")
    event = record_event(
        actor=actor,
        action="property.updated",
        entity_type="Property",
        entity_id="p-123",
        before_state={"status": "draft"},
        after_state={"status": "active"},
        request=request,
    )
    assert event.actor == actor
    assert event.ip_address == "203.0.113.10"
    assert event.user_agent == "OweruTest/1.0"
    assert event.before_state == {"status": "draft"}
    assert event.after_state == {"status": "active"}
    assert event.entity_id == "p-123"


def test_events_are_immutable_through_instance_and_queryset():
    event = record_event(action="test", entity_type="Test")
    event.action = "changed"
    with pytest.raises(RuntimeError):
        event.save()
    with pytest.raises(RuntimeError):
        event.delete()
    with pytest.raises(RuntimeError):
        AuditEvent.objects.filter(pk=event.pk).update(action="changed")
    with pytest.raises(RuntimeError):
        AuditEvent.objects.filter(pk=event.pk).delete()


def test_audit_event_actor_cannot_be_deleted_to_rewrite_history():
    actor = User.objects.create_user(phone="+255700123456", full_name="Asha", password="Strong-pass-482!")
    record_event(actor=actor, action="role.assigned", entity_type="UserRole")
    with pytest.raises(ProtectedError):
        actor.delete()


def test_no_audit_api_is_exposed_to_authenticated_or_anonymous_clients():
    assert APIClient().get("/api/v1/audit/").status_code == 404
    user = User.objects.create_user(phone="+255700123456", full_name="Asha", password="Strong-pass-482!")
    client = APIClient()
    client.force_authenticate(user=user)
    assert client.get("/api/v1/audit/").status_code == 404


def test_sensitive_access_uses_the_audit_event_stream():
    actor = User.objects.create_user(phone="+255700123456", full_name="Asha", password="Strong-pass-482!")
    event = record_sensitive_access(actor=actor, entity_type="BankAccount", entity_id="bank-9")
    assert event.action == "sensitive_data.accessed"
    assert event.actor == actor
