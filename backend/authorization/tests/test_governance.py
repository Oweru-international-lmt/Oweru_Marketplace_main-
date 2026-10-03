from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.apps import apps
from django.contrib import admin
from django.contrib.auth.models import AnonymousUser
from django.db import connection, IntegrityError, transaction
from django.core.management import call_command
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from audit.models import AuditEvent
from authorization.catalog import CATALOG, DEFAULT_ROLE_PERMISSIONS
from authorization.models import Role, Permission, RolePermission, UserRole
from authorization.permissions import HasMarketplaceRole, HasMarketplacePermission, IsManagement, IsSelf
from authorization.services import assign_role, revoke_role, grant_permission, revoke_permission, bootstrap_management

pytestmark = pytest.mark.django_db
BASE = "/api/v1/management/authorization/"


@pytest.fixture
def manager():
    user = User.objects.create_superuser(email="manager@test.test", phone="1", full_name="Manager", password="Strong-pass-482!")
    bootstrap_management(user=user)
    return user


@pytest.fixture
def target():
    return User.objects.create_user(email="staff@test.test", phone="2", full_name="Staff", password="Strong-pass-482!", account_category="operational")


@pytest.fixture
def public():
    return User.objects.create_user(email="public@test.test", phone="3", full_name="Public", password="Strong-pass-482!")


def client(user=None):
    result = APIClient()
    if user:
        result.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return result


def test_catalog_and_frozen_seed_match():
    snapshot = import_module("authorization.migrations.0002_permission_catalog")
    assert snapshot.CATALOG == CATALOG
    assert set(Permission.objects.values_list("code", flat=True)) == set(CATALOG)
    for role, codes in DEFAULT_ROLE_PERMISSIONS.items():
        assert set(Permission.objects.filter(role_permissions__role__code=role).values_list("code", flat=True)) == codes
    assert "outbox.send" not in DEFAULT_ROLE_PERMISSIONS["verifier"]
    assert "verification.order" not in DEFAULT_ROLE_PERMISSIONS["management"]
    assert not any("bank" in code for code in CATALOG)


def test_seed_is_idempotent_and_preserves_optional_grant(manager):
    grant_permission(role_code="verifier", permission_code="outbox.send", actor=manager)
    counts = (Permission.objects.count(), RolePermission.objects.count(), AuditEvent.objects.count())
    seed = import_module("authorization.migrations.0002_permission_catalog").seed_catalog
    editor = SimpleNamespace(connection=connection)
    seed(apps, editor)
    seed(apps, editor)
    assert counts == (Permission.objects.count(), RolePermission.objects.count(), AuditEvent.objects.count())


def test_assign_revoke_reactivate_idempotency_and_audit(manager, target):
    request = APIRequestFactory().post("/", REMOTE_ADDR="192.0.2.1", HTTP_USER_AGENT="Test")
    relation = assign_role(user=target, role_code="verifier", assigned_by=manager, request=request)
    count = AuditEvent.objects.count()
    assert assign_role(user=target, role_code="verifier", assigned_by=manager).pk == relation.pk
    assert AuditEvent.objects.count() == count
    assert target.has_marketplace_permission("verification.record_result")
    assert revoke_role(user=target, role_code="verifier", revoked_by=manager)
    assert not target.has_marketplace_permission("verification.record_result")

    assert not revoke_role(user=target, role_code="verifier", revoked_by=manager)
    assert assign_role(user=target, role_code="verifier", assigned_by=manager).pk == relation.pk
    event = AuditEvent.objects.filter(action="role.assigned", entity_id=str(relation.pk)).earliest("created_at")
    assert event.actor == manager and event.ip_address == "192.0.2.1" and event.user_agent == "Test"
    assert event.after_state == {"user_id": str(target.pk), "role": "verifier", "is_active": True}
    assert target.has_role("verifier")


@pytest.mark.parametrize("role", ["management", "verifier", "marketer", "professional", "local_official", "owner", "agent", "buyer"])
def test_public_cannot_self_assign_any_role(public, role):
    with pytest.raises(PermissionDenied):
        assign_role(user=public, role_code=role, assigned_by=public)


def test_missing_actor_denied(target):
    with pytest.raises(PermissionDenied):
        assign_role(user=target, role_code="verifier")


@pytest.mark.parametrize("role", ["management", "professional", "local_official", "owner", "agent", "buyer"])
def test_management_cannot_bypass_deferred_onboarding(manager, target, role):
    with pytest.raises(ValidationError):
        assign_role(user=target, role_code=role, assigned_by=manager)


def test_management_cannot_assign_to_self(manager):
    with pytest.raises(PermissionDenied):
        assign_role(user=manager, role_code="verifier", assigned_by=manager)


def test_public_category_cannot_be_promoted_even_without_roles(manager, public):
    with pytest.raises(ValidationError):
        assign_role(user=public, role_code="verifier", assigned_by=manager)


def test_revoked_public_history_cannot_be_bypassed(manager, target):
    UserRole.objects.create(user=target, role=Role.objects.get(code="buyer"), is_active=False)
    with pytest.raises(ValidationError):
        assign_role(user=target, role_code="verifier", assigned_by=manager)


@pytest.mark.parametrize("operation", ["assign", "revoke", "grant", "remove"])
def test_unauthorized_mutations(public, target, operation):
    with pytest.raises(PermissionDenied):
        if operation == "assign":
            assign_role(user=target, role_code="verifier", assigned_by=public)
        elif operation == "revoke":
            revoke_role(user=target, role_code="verifier", revoked_by=public)
        elif operation == "grant":
            grant_permission(role_code="verifier", permission_code="outbox.send", actor=public)
        else:
            revoke_permission(role_code="verifier", permission_code="outbox.send", actor=public)


def test_optional_permission_grant_revoke_and_audit(manager, target):
    assign_role(user=target, role_code="verifier", assigned_by=manager)
    grant = grant_permission(role_code="verifier", permission_code="outbox.send", actor=manager)
    count = AuditEvent.objects.count()
    assert grant_permission(role_code="verifier", permission_code="outbox.send", actor=manager).pk == grant.pk
    assert AuditEvent.objects.count() == count
    assert target.has_marketplace_permission("outbox.send")
    assert revoke_permission(role_code="verifier", permission_code="outbox.send", actor=manager)
    assert not target.has_marketplace_permission("outbox.send")
    assert not revoke_permission(role_code="verifier", permission_code="outbox.send", actor=manager)
    assert AuditEvent.objects.filter(action="permission.granted", entity_id=str(grant.pk), actor=manager).exists()
    assert AuditEvent.objects.filter(action="permission.revoked", entity_id=str(grant.pk), actor=manager).exists()


@pytest.mark.parametrize("operation", [grant_permission, revoke_permission])
def test_canonical_matrix_cannot_be_changed(manager, operation):
    with pytest.raises(PermissionDenied):
        operation(role_code="verifier", permission_code="authorization.assign_role", actor=manager)


@pytest.mark.parametrize("operation", [grant_permission, revoke_permission])
def test_invalid_permission_rejected(manager, operation):
    with pytest.raises(ValidationError):
        operation(role_code="verifier", permission_code="TASK_CREATE", actor=manager)


@pytest.mark.parametrize("operation", [assign_role, revoke_role])
def test_invalid_role_rejected(manager, target, operation):
    kwargs = {"assigned_by" if operation == assign_role else "revoked_by": manager}
    with pytest.raises(ValidationError):
        operation(user=target, role_code="director", **kwargs)


@pytest.mark.parametrize("operation", ["assign", "revoke", "grant", "remove"])
def test_audit_failure_rolls_back_mutation(manager, target, operation):
    if operation == "revoke":
        assign_role(user=target, role_code="verifier", assigned_by=manager)
    if operation == "remove":
        grant_permission(role_code="verifier", permission_code="outbox.send", actor=manager)
    before = (list(UserRole.objects.values_list("pk", "is_active")), list(RolePermission.objects.values_list("pk", flat=True)), AuditEvent.objects.count())
    with patch("authorization.services.record_event", side_effect=RuntimeError("audit failed")), pytest.raises(RuntimeError):
        if operation == "assign":
            assign_role(user=target, role_code="verifier", assigned_by=manager)
        elif operation == "revoke":
            revoke_role(user=target, role_code="verifier", revoked_by=manager)
        elif operation == "grant":
            grant_permission(role_code="verifier", permission_code="outbox.send", actor=manager)
        else:
            revoke_permission(role_code="verifier", permission_code="outbox.send", actor=manager)
    assert before == (list(UserRole.objects.values_list("pk", "is_active")), list(RolePermission.objects.values_list("pk", flat=True)), AuditEvent.objects.count())


@pytest.mark.parametrize("disabled", ["user", "role", "assignment", "grant"])
def test_effective_permission_stops_immediately(manager, target, disabled):
    relation = assign_role(user=target, role_code="verifier", assigned_by=manager)
    assert target.has_marketplace_permission("verification.record_result")
    if disabled == "user":
        target.is_active = False
        target.save()
    elif disabled == "role":
        Role.objects.filter(code="verifier").update(is_active=False)
    elif disabled == "assignment":
        revoke_role(user=target, role_code="verifier", revoked_by=manager)
    else:
        RolePermission.objects.filter(role=relation.role, permission__code="verification.record_result").delete()
    assert not target.has_marketplace_permission("verification.record_result")
    request = SimpleNamespace(user=target)
    assert not HasMarketplacePermission().has_permission(request, SimpleNamespace(required_marketplace_permission="verification.record_result"))


def test_inactive_actor_target_and_role_denied(manager, target):
    target.is_active = False
    target.save()
    with pytest.raises(ValidationError):
        assign_role(user=target, role_code="verifier", assigned_by=manager)
    target.is_active = True
    target.save()
    Role.objects.filter(code="verifier").update(is_active=False)
    with pytest.raises(ValidationError):
        assign_role(user=target, role_code="verifier", assigned_by=manager)
    User.objects.filter(pk=manager.pk).update(is_active=False)
    with pytest.raises(PermissionDenied):
        assign_role(user=target, role_code="marketer", assigned_by=manager)


def test_permission_classes_fail_closed(public):
    empty = SimpleNamespace()
    for user in (AnonymousUser(), public):
        request = SimpleNamespace(user=user)
        assert not HasMarketplaceRole().has_permission(request, empty)
        assert not HasMarketplacePermission().has_permission(request, empty)
        assert not IsManagement().has_permission(request, empty)
    public.is_active = False
    request = SimpleNamespace(user=public)
    assert not IsSelf().has_permission(request, empty)
    assert not IsSelf().has_object_permission(request, empty, public)


def test_self_owned_resource_and_missing_owner(public, target):
    request = SimpleNamespace(user=public)
    assert IsSelf().has_object_permission(request, None, SimpleNamespace(user_id=public.pk))
    assert not IsSelf().has_object_permission(request, None, SimpleNamespace(user_id=target.pk))
    assert not IsSelf().has_object_permission(request, None, SimpleNamespace())


@pytest.mark.parametrize("path", ["roles/", "permissions/", "roles/verifier/permissions/"])
def test_management_read_api_access(manager, public, path):
    assert client().get(BASE + path).status_code == 401
    assert client(public).get(BASE + path).status_code == 403
    response = client(manager).get(BASE + path)
    assert response.status_code == 200
    assert not {"password", "token", "email", "phone", "locked_until"} & set(response.data[0])


def test_management_mutation_api(manager, target, public):
    path = BASE + f"users/{target.pk}/roles/"
    assert client().post(path + "assign/", {"role_code": "verifier"}).status_code == 401
    assert client(public).post(path + "assign/", {"role_code": "verifier"}).status_code == 403
    c = client(manager)
    assert c.post(path + "assign/", {"role_code": "verifier"}).status_code == 200
    assert c.get(path).data == [{"role_code": "verifier", "is_active": True}]
    assert c.post(path + "assign/", {"role_code": "management"}).status_code == 400
    assert c.post(path + "assign/", {"role_code": "INVALID"}).status_code == 400
    assert c.post(path + "revoke/", {"role_code": "verifier"}).status_code == 204
    assert not target.has_role("verifier")


def test_outbox_api_is_narrow(manager, public):
    path = BASE + "roles/verifier/outbox-send/"
    assert client(public).put(path, {"enabled": True}, format="json").status_code == 403
    assert client(manager).put(path, {"enabled": True}, format="json").status_code == 200
    assert client(manager).put(path, {"enabled": False}, format="json").status_code == 200
    assert client(manager).put(BASE + "roles/buyer/outbox-send/", {"enabled": True}, format="json").status_code == 403
    assert client(manager).post(BASE + "roles/verifier/permissions/", {"permission_code": "payment.confirm"}).status_code == 405


def test_management_needs_explicit_grant(manager, target):
    RolePermission.objects.filter(role__code="management", permission__code="authorization.assign_role").delete()
    assert client(manager).post(BASE + f"users/{target.pk}/roles/assign/", {"role_code": "verifier"}).status_code == 403
    with pytest.raises(PermissionDenied):
        assign_role(user=target, role_code="verifier", assigned_by=manager)


def test_superuser_is_not_marketplace_management(target):
    target.is_superuser = target.is_staff = True
    target.save()
    assert client(target).get(BASE + "roles/").status_code == 403


def test_registration_only_assigns_buyer_and_audits():
    response = client().post("/api/v1/auth/register/", {"email": "new@test.test", "phone": "99", "full_name": "New", "password": "Strong-pass-482!", "role": "management", "account_category": "operational", "is_superuser": True}, format="json")
    assert response.status_code == 201
    user = User.objects.get(pk=response.data["id"])
    assert user.account_category == "public" and not user.is_superuser and not user.is_staff
    assert list(user.user_roles.values_list("role__code", flat=True)) == ["buyer"]
    assert AuditEvent.objects.filter(actor=user, action="role.assigned").exists()


def test_registration_audit_failure_rolls_back_user():
    from authorization.services import register_public_user
    with patch("authorization.services.record_event", side_effect=RuntimeError), pytest.raises(RuntimeError):
        register_public_user(email="new@test.test", phone="99", full_name="New", password="Strong-pass-482!")
    assert not User.objects.filter(email="new@test.test").exists()


def test_admin_has_no_mutation_bypass(manager):
    request = SimpleNamespace(user=manager)
    for model in (Role, Permission, RolePermission, UserRole, AuditEvent):
        model_admin = admin.site._registry[model]
        assert not model_admin.has_add_permission(request)
        assert not model_admin.has_change_permission(request)
        assert not model_admin.has_delete_permission(request)


def test_bootstrap_command_idempotent_and_restricted(manager, public):
    count = AuditEvent.objects.count()
    call_command("bootstrap_marketplace_management", user_id=str(manager.pk))
    assert AuditEvent.objects.count() == count
    with pytest.raises(PermissionDenied):
        bootstrap_management(user=public)


def test_category_database_constraint(target):
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.filter(pk=target.pk).update(account_category="invalid")


def test_stale_user_object_does_not_retain_access(manager, target):
    assign_role(user=target, role_code="verifier", assigned_by=manager)
    User.objects.filter(pk=target.pk).update(is_active=False)
    assert target.is_active  # Deliberately stale instance.
    assert not target.has_role("verifier")
    assert not target.has_marketplace_permission("verification.record_result")
    assert not IsSelf().has_object_permission(SimpleNamespace(user=target), None, target)


def test_inconsistent_category_assignment_never_grants_access(public):
    UserRole.objects.create(user=public, role=Role.objects.get(code="management"))
    assert not public.has_role("management")
    assert not public.has_marketplace_permission("authorization.assign_role")


def test_inactive_jwt_user_is_denied(manager):
    c = client(manager)
    User.objects.filter(pk=manager.pk).update(is_active=False)
    assert c.get(BASE + "roles/").status_code == 401


def test_revoked_management_role_is_denied(manager, target):
    manager.user_roles.update(is_active=False)
    assert client(manager).get(BASE + "roles/").status_code == 403
    with pytest.raises(PermissionDenied):
        assign_role(user=target, role_code="verifier", assigned_by=manager)


def test_revocation_still_works_for_inactive_target_and_role(manager, target):
    assign_role(user=target, role_code="verifier", assigned_by=manager)
    User.objects.filter(pk=target.pk).update(is_active=False)
    Role.objects.filter(code="verifier").update(is_active=False)
    assert revoke_role(user=target, role_code="verifier", revoked_by=manager)


def test_role_list_needs_explicit_management_view_permission(manager):
    RolePermission.objects.filter(role__code="management", permission__code="authorization.view").delete()
    assert client(manager).get(BASE + "roles/").status_code == 403


def test_user_role_read_endpoint_is_protected_and_minimal(manager, target, public):
    path = BASE + f"users/{target.pk}/roles/"
    assert client().get(path).status_code == 401
    assert client(public).get(path).status_code == 403
    assign_role(user=target, role_code="marketer", assigned_by=manager)
    assert client(manager).get(path).data == [{"role_code": "marketer", "is_active": True}]


def test_api_cannot_convert_public_account(manager, public):
    response = client(manager).post(BASE + f"users/{public.pk}/roles/assign/", {"role_code": "verifier"})
    assert response.status_code == 400
    assert not public.user_roles.exists()


def test_bootstrap_audit_failure_rolls_back(target):
    target.is_staff = target.is_superuser = True
    target.save()
    with patch("authorization.services.record_event", side_effect=RuntimeError), pytest.raises(RuntimeError):
        bootstrap_management(user=target)
    assert not target.user_roles.exists()


def test_ordinary_superuser_cannot_view_authorization_admin(target):
    target.is_superuser = target.is_staff = True
    target.save()
    request = SimpleNamespace(user=target)
    assert not admin.site._registry[Role].has_view_permission(request)
    assert not admin.site._registry[AuditEvent].has_view_permission(request)


def test_failed_reactivation_rolls_back_state_and_actor(manager, target):
    assignment = assign_role(user=target, role_code="verifier", assigned_by=manager)
    revoke_role(user=target, role_code="verifier", revoked_by=manager)
    count = AuditEvent.objects.count()
    with patch("authorization.services.record_event", side_effect=RuntimeError), pytest.raises(RuntimeError):
        assign_role(user=target, role_code="verifier", assigned_by=manager)
    assignment.refresh_from_db()
    assert not assignment.is_active
    assert AuditEvent.objects.count() == count


def test_failed_grant_delete_rolls_back_audit(manager):
    grant = grant_permission(role_code="marketer", permission_code="outbox.send", actor=manager)
    count = AuditEvent.objects.count()
    with patch.object(RolePermission, "delete", side_effect=RuntimeError), pytest.raises(RuntimeError):
        revoke_permission(role_code="marketer", permission_code="outbox.send", actor=manager)
    assert RolePermission.objects.filter(pk=grant.pk).exists()
    assert AuditEvent.objects.count() == count


def test_inactive_management_role_denies_api_and_service(manager, target):
    Role.objects.filter(code="management").update(is_active=False)
    assert client(manager).get(BASE + "roles/").status_code == 403
    with pytest.raises(PermissionDenied):
        assign_role(user=target, role_code="verifier", assigned_by=manager)


def test_anonymous_self_object_permission_is_denied(public):
    assert not IsSelf().has_object_permission(SimpleNamespace(user=AnonymousUser()), None, public)


@pytest.mark.parametrize("role", ["buyer", "owner", "agent", "management", "local_official", "professional"])
def test_optional_outbox_grant_cannot_escape_staff_allowlist(manager, role):
    with pytest.raises(PermissionDenied):
        grant_permission(role_code=role, permission_code="outbox.send", actor=manager)


def test_invalid_outbox_role_and_missing_boolean_return_validation_errors(manager):
    c = client(manager)
    assert c.put(BASE + "roles/invalid/outbox-send/", {"enabled": True}, format="json").status_code == 400
    assert c.put(BASE + "roles/verifier/outbox-send/", {}, format="json").status_code == 400


def test_catalog_response_and_role_matrix_are_exact(manager):
    c = client(manager)
    assert {row["code"] for row in c.get(BASE + "permissions/").data} == set(CATALOG)
    for role, expected in DEFAULT_ROLE_PERMISSIONS.items():
        response = c.get(BASE + f"roles/{role}/permissions/")
        assert response.status_code == 200
        assert {row["code"] for row in response.data} == expected


def test_management_revoke_api_denies_ordinary_user(manager, target, public):
    assign_role(user=target, role_code="verifier", assigned_by=manager)
    path = BASE + f"users/{target.pk}/roles/revoke/"
    assert client().post(path, {"role_code": "verifier"}).status_code == 401
    assert client(public).post(path, {"role_code": "verifier"}).status_code == 403
    assert target.has_role("verifier")


def test_management_api_never_uses_session_authentication(manager):
    c = APIClient()
    c.force_login(manager)
    assert c.get(BASE + "roles/").status_code == 401


def test_account_lookup_is_exact_email_only_and_minimal(manager, target, public):
    path = BASE + "users/"
    assert client().get(path, {"email": target.email}).status_code == 401
    assert client(public).get(path, {"email": target.email}).status_code == 403
    c = client(manager)
    assert c.get(path).status_code == 400
    response = c.get(path, {"email": "  STAFF@test.test "})
    assert response.status_code == 200
    assert response.data == [{"id": str(target.pk), "full_name": "Staff", "account_category": "operational", "is_active": True}]
    assert c.get(path, {"email": "staff@test"}).data == []
    assert c.get(path, {"email": "nobody@test.test"}).data == []


def test_account_lookup_needs_explicit_view_permission(manager, target):
    RolePermission.objects.filter(role__code="management", permission__code="authorization.view").delete()
    assert client(manager).get(BASE + "users/", {"email": target.email}).status_code == 403


def test_me_reports_effective_roles_and_permissions(manager, target, public):
    me = client(manager).get("/api/v1/auth/me/").data
    assert me["account_category"] == "operational"
    assert me["roles"] == ["management"]
    assert me["permissions"] == sorted(DEFAULT_ROLE_PERMISSIONS["management"])

    assign_role(user=target, role_code="verifier", assigned_by=manager)
    assert client(target).get("/api/v1/auth/me/").data["roles"] == ["verifier"]
    revoke_role(user=target, role_code="verifier", revoked_by=manager)
    me = client(target).get("/api/v1/auth/me/").data
    assert me["roles"] == [] and me["permissions"] == []

    # An inconsistent assignment grants nothing, so it is not reported either.
    UserRole.objects.create(user=public, role=Role.objects.get(code="management"))
    assert client(public).get("/api/v1/auth/me/").data["roles"] == []


def test_registration_and_login_return_buyer_access():
    data = {"email": "new@test.test", "phone": "9", "full_name": "New", "password": "Strong-pass-482!"}
    assert APIClient().post("/api/v1/auth/register/", data, format="json").data["roles"] == ["buyer"]
    user = APIClient().post("/api/v1/auth/login/", {"email": data["email"], "password": data["password"]}, format="json").data["user"]
    assert user["roles"] == ["buyer"]
    assert user["permissions"] == sorted(DEFAULT_ROLE_PERMISSIONS["buyer"])
