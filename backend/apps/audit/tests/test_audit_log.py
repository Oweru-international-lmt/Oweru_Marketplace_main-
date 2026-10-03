import pytest
from django.contrib import admin
from django.db.models.deletion import ProtectedError
from rest_framework.test import APIRequestFactory

from apps.accounts.models import User
from apps.audit.admin import AuditLogAdmin
from apps.audit.models import AuditLog
from apps.audit.services import create_audit_log, record_sensitive_access


pytestmark = pytest.mark.django_db


def create_user(email="asha@example.test"):
    return User.objects.create_user(
        email=email,
        phone="+255700123456",
        full_name="Asha Mushi",
        password="Strong-pass-482!",
    )


def test_create_audit_log_records_actor_metadata_and_state():
    actor = create_user()
    request = APIRequestFactory().get("/internal/", REMOTE_ADDR="203.0.113.10", HTTP_USER_AGENT="OweruTest/1.0")
    request.user = actor

    log = create_audit_log(
        action="account.updated",
        entity_type="User",
        entity_id=actor.pk,
        before={"full_name": "Asha"},
        after={"full_name": "Asha Mushi"},
        request=request,
    )

    assert log.actor == actor
    assert log.before == {"full_name": "Asha"}
    assert log.after == {"full_name": "Asha Mushi"}
    assert log.ip_address == "203.0.113.10"
    assert log.user_agent == "OweruTest/1.0"
    assert log.created_at is not None


def test_audit_log_is_append_only_through_model_and_queryset_operations():
    log = create_audit_log(action="test.created", entity_type="Test")
    log.action = "test.changed"

    with pytest.raises(RuntimeError):
        log.save()
    with pytest.raises(RuntimeError):
        log.delete()
    with pytest.raises(RuntimeError):
        AuditLog.objects.filter(pk=log.pk).update(action="test.changed")
    with pytest.raises(RuntimeError):
        AuditLog.objects.filter(pk=log.pk).delete()
    with pytest.raises(RuntimeError):
        AuditLog.objects.update_or_create(pk=log.pk, defaults={"action": "test.changed"})
    with pytest.raises(RuntimeError):
        AuditLog.objects.bulk_update([log], ["action"])


def test_audit_actor_is_protected_from_deletion():
    actor = create_user()
    create_audit_log(actor=actor, action="account.viewed", entity_type="User", entity_id=actor.pk)

    with pytest.raises(ProtectedError):
        actor.delete()


def test_admin_does_not_allow_add_change_or_delete():
    model_admin = AuditLogAdmin(AuditLog, admin.site)
    request = APIRequestFactory().get("/admin/")
    request.user = create_user()

    assert not model_admin.has_add_permission(request)
    assert not model_admin.has_change_permission(request)
    assert not model_admin.has_delete_permission(request)


def test_sensitive_access_helper_uses_audit_log_stream():
    actor = create_user()

    log = record_sensitive_access(actor=actor, entity_type="IdentityDocument", entity_id="doc-1")

    assert log.actor == actor
    assert log.action == "sensitive_data.accessed"
    assert log.entity_type == "IdentityDocument"
    assert log.entity_id == "doc-1"
