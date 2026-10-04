import pytest
from unittest.mock import patch
from django.apps import apps
from django.contrib.auth.models import AnonymousUser
from django.db import IntegrityError, transaction
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.accounts.serializers import UserPrivateProfileSerializer, UserPublicSerializer
from apps.audit.models import AuditLog
from apps.roles.audit_events import (
    RBAC_AUDIT_ACTIONS,
    ROLE_ASSIGNED,
    ROLE_REMOVED,
    SENSITIVE_DATA_ACCESSED,
    SETTINGS_CHANGED,
    USER_RESTORED,
    USER_SUSPENDED,
)
from apps.roles.catalog import (
    CANONICAL_ROLE_CODES,
    CANONICAL_ROLE_DEFINITIONS,
    ROLE_AGENT,
    ROLE_BUYER,
    ROLE_LOCAL_OFFICIAL,
    ROLE_MANAGEMENT,
    ROLE_MARKETER,
    ROLE_OWNER,
    ROLE_PROFESSIONAL,
    ROLE_VERIFIER,
)
from apps.roles.legacy_authorization.models import UserRole as LegacyUserRole
from apps.roles.legacy_authorization.models import Role as LegacyRole
from apps.roles.legacy_authorization.services import bootstrap_management as bootstrap_legacy_management
from apps.roles.models import Role, UserRole
from apps.roles.permissions import (
    CanConfirmPayment,
    CanManageLead,
    CanManageVerification,
    CanViewSensitiveOwnerData,
    IsLister,
    IsListingOwner,
    IsLocalOfficial,
    IsManagement,
    IsMarketer,
    IsProfessional,
    IsVerifier,
)
from apps.roles.services import assign_role, bootstrap_canonical_roles, remove_role, user_has_role


pytestmark = pytest.mark.django_db


def create_user(email):
    return User.objects.create_user(
        email=email,
        phone=f"+2557{abs(hash(email)) % 100000000:08d}",
        full_name="Test User",
        password="Strong-pass-482!",
    )


def request_for(user):
    request = APIRequestFactory().get("/internal/")
    request.user = user
    return request


def api_client(user=None):
    client = APIClient()
    if user:
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


def create_management_actor(email="canonical-manager@example.test"):
    manager = create_user(email)
    UserRole.objects.create(user=manager, role=Role.objects.get(code=ROLE_MANAGEMENT))
    return manager


ROLE_PERMISSION_EXPECTATIONS = {
    ROLE_OWNER: [IsLister],
    ROLE_AGENT: [IsLister],
    ROLE_LOCAL_OFFICIAL: [IsLocalOfficial],
    ROLE_PROFESSIONAL: [IsProfessional],
    ROLE_VERIFIER: [IsVerifier],
    ROLE_MARKETER: [IsMarketer],
    ROLE_MANAGEMENT: [IsManagement],
}

ALL_CANONICAL_PERMISSION_CLASSES = (
    IsManagement,
    IsVerifier,
    IsMarketer,
    IsProfessional,
    IsLocalOfficial,
    IsLister,
)


def permission_result(permission_class, user):
    return permission_class().has_permission(request_for(user), view=None)


def test_role_code_is_unique_and_assignment_uses_auth_user_model():
    user = create_user("asha@example.test")
    actor = create_user("manager@example.test")
    role = Role.objects.get(code="management")

    assignment = UserRole.objects.create(user=user, role=role, assigned_by=actor)

    assert str(role) == "Management"
    assert assignment.user == user
    assert assignment.assigned_by == actor
    assert assignment.assigned_at is not None
    with pytest.raises(IntegrityError):
        Role.objects.create(code="management", name="Duplicate")


def test_duplicate_active_user_role_assignment_is_prevented_but_inactive_history_is_allowed():
    user = create_user("asha@example.test")
    role = Role.objects.get(code="verifier")
    UserRole.objects.create(user=user, role=role)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            UserRole.objects.create(user=user, role=role)

    UserRole.objects.create(user=user, role=role, is_active=False)
    assert UserRole.objects.filter(user=user, role=role).count() == 2


@pytest.mark.parametrize(
    ("permission_class", "role_code"),
    [
        (IsManagement, "management"),
        (IsVerifier, "verifier"),
        (IsMarketer, "marketer"),
        (IsProfessional, "professional"),
        (IsLocalOfficial, "local_official"),
    ],
)
def test_role_permission_classes_require_matching_active_role(permission_class, role_code):
    user = create_user(f"{role_code}@example.test")
    role = Role.objects.get(code=role_code)
    permission = permission_class()

    assert not permission.has_permission(request_for(user), view=None)

    UserRole.objects.create(user=user, role=role)
    assert permission.has_permission(request_for(user), view=None)

    role.is_active = False
    role.save(update_fields=["is_active", "updated_at"])
    assert not permission.has_permission(request_for(user), view=None)


@pytest.mark.parametrize(
    ("permission_class", "role_code"),
    [
        (IsManagement, "management"),
        (IsVerifier, "verifier"),
        (IsMarketer, "marketer"),
        (IsProfessional, "professional"),
        (IsLocalOfficial, "local_official"),
        (IsLister, ROLE_OWNER),
        (IsLister, ROLE_AGENT),
    ],
)
def test_role_permission_classes_ignore_inactive_assignments(permission_class, role_code):
    user = create_user("inactive-assignment@example.test")
    role = Role.objects.get(code=role_code)
    UserRole.objects.create(user=user, role=role, is_active=False)

    assert not user_has_role(user, role_code)
    assert not permission_class().has_permission(request_for(user), view=None)


def test_user_has_role_fails_closed_for_unauthenticated_inactive_and_nonexistent_roles():
    user = create_user("closed@example.test")
    UserRole.objects.create(user=user, role=Role.objects.get(code=ROLE_MANAGEMENT))

    assert not user_has_role(AnonymousUser(), ROLE_MANAGEMENT)
    assert not user_has_role(user, "not_a_role")
    user.is_active = False
    user.save(update_fields=["is_active"])
    assert not user_has_role(user, ROLE_MANAGEMENT)


@pytest.mark.parametrize("user", [None, AnonymousUser()])
def test_unauthenticated_role_check_does_not_query_database(user, django_assert_num_queries):
    with django_assert_num_queries(0):
        assert not user_has_role(user, ROLE_MANAGEMENT)


def test_role_check_denies_missing_required_role_row():
    user = create_user("missing-role@example.test")
    Role.objects.filter(code=ROLE_OWNER).delete()

    assert not user_has_role(user, ROLE_OWNER)
    assert not IsLister().has_permission(request_for(user), view=None)


def test_role_check_denies_account_deactivated_after_user_was_loaded():
    user = create_user("deactivated@example.test")
    UserRole.objects.create(user=user, role=Role.objects.get(code=ROLE_MANAGEMENT))
    assert user_has_role(user, ROLE_MANAGEMENT)

    User.objects.filter(pk=user.pk).update(is_active=False)

    assert user.is_active
    assert not user_has_role(user, ROLE_MANAGEMENT)
    assert not IsManagement().has_permission(request_for(user), view=None)


def test_canonical_catalog_contains_exact_required_oweru_roles():
    assert CANONICAL_ROLE_CODES == {
        "buyer",
        "owner",
        "agent",
        "local_official",
        "professional",
        "verifier",
        "marketer",
        "management",
    }
    assert set(Role.objects.values_list("code", flat=True)) >= CANONICAL_ROLE_CODES
    assert {role.code for role in Role.objects.filter(code__in=CANONICAL_ROLE_CODES)} == CANONICAL_ROLE_CODES


def test_canonical_bootstrap_creates_missing_roles():
    Role.objects.filter(code__in=["buyer", "owner"]).delete()
    assert not Role.objects.filter(code="buyer").exists()

    bootstrap_canonical_roles()

    assert Role.objects.get(code="buyer").name == CANONICAL_ROLE_DEFINITIONS["buyer"]
    assert Role.objects.get(code="owner").name == CANONICAL_ROLE_DEFINITIONS["owner"]


def test_canonical_bootstrap_is_idempotent_and_creates_no_duplicates():
    before = Role.objects.count()

    first = bootstrap_canonical_roles()
    second = bootstrap_canonical_roles()

    assert len(first) == len(second) == 8
    assert Role.objects.count() == before
    for code in CANONICAL_ROLE_CODES:
        assert Role.objects.filter(code=code).count() == 1


def test_canonical_bootstrap_preserves_existing_assignments():
    user = create_user("assigned@example.test")
    role = Role.objects.get(code="buyer")
    assignment = UserRole.objects.create(user=user, role=role)

    bootstrap_canonical_roles()

    assignment.refresh_from_db()
    assert assignment.user == user
    assert assignment.role == role
    assert assignment.is_active


def test_canonical_bootstrap_does_not_delete_unknown_custom_roles():
    custom = Role.objects.create(code="custom_reviewer", name="Custom reviewer")

    bootstrap_canonical_roles()

    custom.refresh_from_db()
    assert custom.name == "Custom reviewer"
    assert Role.objects.filter(code="custom_reviewer").count() == 1


def test_legacy_authorization_eight_role_behavior_remains_compatible():
    assert set(LegacyRole.objects.values_list("code", flat=True)) == CANONICAL_ROLE_CODES


def test_unauthenticated_user_fails_all_role_permissions():
    request = request_for(AnonymousUser())

    for permission in (IsManagement(), IsVerifier(), IsMarketer(), IsProfessional(), IsLocalOfficial(), IsLister()):
        assert not permission.has_permission(request, view=None)


@pytest.mark.parametrize(
    ("permission_class", "role_code"),
    [
        (IsManagement, "management"),
        (IsVerifier, "verifier"),
        (IsMarketer, "marketer"),
        (IsProfessional, "professional"),
        (IsLocalOfficial, "local_official"),
    ],
)
@pytest.mark.parametrize("assigned_role_code", sorted(CANONICAL_ROLE_CODES))
def test_named_role_permissions_require_the_exact_role(permission_class, role_code, assigned_role_code):
    user = create_user("exact-role@example.test")
    UserRole.objects.create(user=user, role=Role.objects.get(code=assigned_role_code))

    assert permission_class().has_permission(request_for(user), view=None) == (assigned_role_code == role_code)


@pytest.mark.parametrize("role_code", [ROLE_OWNER, ROLE_AGENT])
def test_is_lister_allows_owner_or_agent(role_code):
    user = create_user(f"{role_code}@lister.test")
    UserRole.objects.create(user=user, role=Role.objects.get(code=role_code))

    assert IsLister().has_permission(request_for(user), view=None)


@pytest.mark.parametrize("role_code", sorted(CANONICAL_ROLE_CODES - {ROLE_OWNER, ROLE_AGENT}))
def test_is_lister_denies_all_other_roles_alone(role_code):
    user = create_user(f"{role_code}@not-lister.test")
    UserRole.objects.create(user=user, role=Role.objects.get(code=role_code))

    assert not IsLister().has_permission(request_for(user), view=None)


@pytest.mark.parametrize("role_code", [ROLE_OWNER, ROLE_AGENT])
def test_is_lister_allows_management_only_when_separately_owner_or_agent(role_code):
    user = create_user("manager-owner@example.test")
    UserRole.objects.create(user=user, role=Role.objects.get(code=ROLE_MANAGEMENT))
    assert not IsLister().has_permission(request_for(user), view=None)

    UserRole.objects.create(user=user, role=Role.objects.get(code=role_code))
    assert IsLister().has_permission(request_for(user), view=None)


def test_inactive_role_and_inactive_assignment_are_denied():
    user = create_user("inactive-role@example.test")
    role = Role.objects.get(code=ROLE_OWNER)
    UserRole.objects.create(user=user, role=role)
    assert IsLister().has_permission(request_for(user), view=None)

    role.is_active = False
    role.save(update_fields=["is_active", "updated_at"])
    assert not IsLister().has_permission(request_for(user), view=None)

    role.is_active = True
    role.save(update_fields=["is_active", "updated_at"])
    UserRole.objects.filter(user=user, role=role).update(is_active=False)
    assert not IsLister().has_permission(request_for(user), view=None)


@pytest.mark.parametrize(
    "permission_class",
    [IsManagement, IsVerifier, IsMarketer, IsProfessional, IsLocalOfficial, IsLister],
)
def test_client_supplied_role_data_cannot_affect_permission_result(permission_class):
    user = create_user("client-claim@example.test")
    raw_request = APIRequestFactory().post(
        "/internal/?role=management",
        {"role": ROLE_MANAGEMENT, "roles": sorted(CANONICAL_ROLE_CODES)},
        format="json",
    )
    request = Request(raw_request)
    request.user = user

    assert not permission_class().has_permission(request, view=None)


def test_client_supplied_role_cannot_override_active_assignment():
    user = create_user("server-assignment@example.test")
    UserRole.objects.create(user=user, role=Role.objects.get(code=ROLE_MANAGEMENT))
    request = Request(APIRequestFactory().post("/internal/", {"role": ROLE_BUYER}, format="json"))
    request.user = user

    assert IsManagement().has_permission(request, view=None)
    assert not IsLister().has_permission(request, view=None)


@pytest.mark.parametrize(
    "permission",
    [
        CanViewSensitiveOwnerData(),
        CanManageLead(),
        CanConfirmPayment(),
        CanManageVerification(),
    ],
)
@pytest.mark.parametrize("authenticated", [False, True])
def test_deferred_domain_permissions_fail_closed(permission, authenticated):
    user = create_user("deferred@example.test")
    for role_code in CANONICAL_ROLE_CODES:
        UserRole.objects.create(user=user, role=Role.objects.get(code=role_code))
    request = request_for(user if authenticated else AnonymousUser())

    assert not permission.has_permission(request, view=None)
    assert not permission.has_object_permission(request, view=None, obj=object())


@pytest.mark.parametrize("role_code", sorted(CANONICAL_ROLE_CODES))
def test_complete_canonical_role_path_and_lifecycle_for_each_role(role_code):
    Role.objects.filter(code=role_code).delete()
    bootstrap_canonical_roles()
    role = Role.objects.get(code=role_code)
    manager = create_management_actor(f"manager-{role_code}@example.test")
    target = create_user(f"path-{role_code}@example.test")

    assignment = assign_role(user=target, role_code=role_code, assigned_by=manager)

    assert assignment.role == role
    assert assignment.assigned_by == manager
    assert user_has_role(target, role_code)
    expected_permissions = ROLE_PERMISSION_EXPECTATIONS.get(role_code, [])
    for permission_class in ALL_CANONICAL_PERMISSION_CLASSES:
        assert permission_result(permission_class, target) == (permission_class in expected_permissions)

    assignment.is_active = False
    assignment.save(update_fields=["is_active"])
    assert not user_has_role(target, role_code)
    for permission_class in ALL_CANONICAL_PERMISSION_CLASSES:
        assert not permission_result(permission_class, target)

    assignment = assign_role(user=target, role_code=role_code, assigned_by=manager)
    role.is_active = False
    role.save(update_fields=["is_active", "updated_at"])
    assert not user_has_role(target, role_code)
    for permission_class in ALL_CANONICAL_PERMISSION_CLASSES:
        assert not permission_result(permission_class, target)

    role.is_active = True
    role.save(update_fields=["is_active", "updated_at"])
    assert remove_role(user=target, role_code=role_code, removed_by=manager)
    assignment.refresh_from_db()
    assert not assignment.is_active
    assert not user_has_role(target, role_code)


def test_canonical_path_layers_agree_for_management_permission():
    bootstrap_canonical_roles()
    manager = create_management_actor()
    target = create_user("canonical-chain@example.test")

    assign_role(user=target, role_code=ROLE_MANAGEMENT, assigned_by=manager)

    assert ROLE_MANAGEMENT in CANONICAL_ROLE_DEFINITIONS
    assert Role.objects.filter(code=ROLE_MANAGEMENT, is_active=True).exists()
    assert UserRole.objects.filter(user=target, role__code=ROLE_MANAGEMENT, is_active=True).exists()
    assert user_has_role(target, ROLE_MANAGEMENT)
    assert IsManagement().has_permission(request_for(target), view=None)


def test_multiple_canonical_roles_do_not_create_hierarchy():
    manager = create_management_actor()
    management_owner = create_user("management-owner@example.test")
    buyer_agent = create_user("buyer-agent@example.test")

    assign_role(user=management_owner, role_code=ROLE_MANAGEMENT, assigned_by=manager)
    assign_role(user=management_owner, role_code=ROLE_OWNER, assigned_by=manager)
    assign_role(user=buyer_agent, role_code=ROLE_BUYER, assigned_by=manager)
    assign_role(user=buyer_agent, role_code=ROLE_AGENT, assigned_by=manager)

    assert IsManagement().has_permission(request_for(management_owner), view=None)
    assert IsLister().has_permission(request_for(management_owner), view=None)
    assert not IsVerifier().has_permission(request_for(management_owner), view=None)
    assert IsLister().has_permission(request_for(buyer_agent), view=None)
    assert not IsManagement().has_permission(request_for(buyer_agent), view=None)
    assert not IsVerifier().has_permission(request_for(buyer_agent), view=None)


def test_canonical_permissions_ignore_legacy_assignments_and_user_has_role_legacy_method():
    manager = User.objects.create_superuser(
        email="legacy-only-manager@example.test",
        phone="+255799100001",
        full_name="Legacy Only Manager",
        password="Strong-pass-482!",
    )
    bootstrap_legacy_management(user=manager)
    target = User.objects.create_user(
        email="legacy-only-target@example.test",
        phone="+255799100002",
        full_name="Legacy Only Target",
        password="Strong-pass-482!",
        account_category="operational",
    )

    response = api_client(manager).post(
        f"/api/v1/management/authorization/users/{target.pk}/roles/assign/",
        {"role_code": "verifier"},
    )

    assert response.status_code == 200
    assert target.has_role("verifier")
    assert not user_has_role(target, ROLE_VERIFIER)
    assert not IsVerifier().has_permission(request_for(target), view=None)
    assert LegacyUserRole.objects.filter(user=target, role__code="verifier", is_active=True).exists()
    assert not UserRole.objects.filter(user=target, role__code=ROLE_VERIFIER).exists()


def test_legacy_permissions_ignore_canonical_assignments():
    manager = create_management_actor()
    target = create_user("canonical-only-target@example.test")

    assign_role(user=target, role_code=ROLE_VERIFIER, assigned_by=manager)

    assert user_has_role(target, ROLE_VERIFIER)
    assert IsVerifier().has_permission(request_for(target), view=None)
    assert not target.has_role("verifier")
    assert not target.has_marketplace_permission("verification.record_result")
    assert UserRole.objects.filter(user=target, role__code=ROLE_VERIFIER, is_active=True).exists()
    assert not LegacyUserRole.objects.filter(user=target, role__code="verifier").exists()


def test_management_actor_can_assign_canonical_role():
    manager = create_management_actor()
    target = create_user("canonical-owner@example.test")

    assignment = assign_role(user=target, role_code=ROLE_OWNER, assigned_by=manager)

    assert assignment.user == target
    assert assignment.role.code == ROLE_OWNER
    assert assignment.assigned_by == manager
    assert user_has_role(target, ROLE_OWNER)


def test_rbac_audit_action_catalog_exposes_current_and_future_actions():
    assert RBAC_AUDIT_ACTIONS[ROLE_ASSIGNED] == "Canonical role assigned"
    assert RBAC_AUDIT_ACTIONS[ROLE_REMOVED] == "Canonical role removed"
    assert {USER_SUSPENDED, USER_RESTORED, SETTINGS_CHANGED, SENSITIVE_DATA_ACCESSED} <= set(RBAC_AUDIT_ACTIONS)


def test_successful_canonical_assignment_creates_role_assigned_audit_event():
    manager = create_management_actor()
    target = create_user("audit-assign-target@example.test")
    request = APIRequestFactory().post("/internal/", REMOTE_ADDR="203.0.113.42", HTTP_USER_AGENT="RBAC-Test/1.0")

    assignment = assign_role(user=target, role_code=ROLE_OWNER, assigned_by=manager, request=request)
    log = AuditLog.objects.get(action=ROLE_ASSIGNED)

    assert log.actor == manager
    assert log.entity_type == "UserRole"
    assert log.entity_id == str(assignment.pk)
    assert log.before == {}
    assert log.after == {"user_id": str(target.pk), "role_code": ROLE_OWNER, "is_active": True}
    assert log.ip_address == "203.0.113.42"
    assert log.user_agent == "RBAC-Test/1.0"


def test_failed_or_unauthorized_canonical_assignment_creates_no_success_audit():
    target = create_user("audit-assign-fail-target@example.test")
    ordinary = create_user("audit-assign-ordinary@example.test")
    manager = create_management_actor("audit-assign-manager@example.test")
    Role.objects.filter(code=ROLE_OWNER).update(is_active=False)

    with pytest.raises(PermissionDenied):
        assign_role(user=target, role_code=ROLE_OWNER, assigned_by=ordinary)
    with pytest.raises(ValidationError):
        assign_role(user=target, role_code=ROLE_OWNER, assigned_by=manager)

    assert not AuditLog.objects.filter(action=ROLE_ASSIGNED).exists()


def test_idempotent_assignment_does_not_create_duplicate_role_assigned_audit():
    manager = create_management_actor()
    target = create_user("audit-idempotent-target@example.test")

    first = assign_role(user=target, role_code=ROLE_OWNER, assigned_by=manager)
    second = assign_role(user=target, role_code=ROLE_OWNER, assigned_by=manager)

    assert first.pk == second.pk
    assert AuditLog.objects.filter(action=ROLE_ASSIGNED, entity_id=str(first.pk)).count() == 1


def test_assignment_audit_failure_rolls_back_canonical_mutation():
    manager = create_management_actor()
    target = create_user("audit-assign-rollback@example.test")

    with patch("apps.roles.services.create_audit_log", side_effect=RuntimeError("audit failed")), pytest.raises(RuntimeError):
        assign_role(user=target, role_code=ROLE_OWNER, assigned_by=manager)

    assert not UserRole.objects.filter(user=target, role__code=ROLE_OWNER).exists()
    assert not AuditLog.objects.filter(action=ROLE_ASSIGNED).exists()


def test_unauthorized_actor_cannot_assign_canonical_role():
    actor = create_user("ordinary-assigner@example.test")
    target = create_user("assign-target@example.test")

    with pytest.raises(PermissionDenied):
        assign_role(user=target, role_code=ROLE_OWNER, assigned_by=actor)
    assert not UserRole.objects.filter(user=target, role__code=ROLE_OWNER).exists()


def test_management_actor_can_remove_canonical_role():
    manager = create_management_actor()
    target = create_user("remove-target@example.test")
    assign_role(user=target, role_code=ROLE_AGENT, assigned_by=manager)

    assert remove_role(user=target, role_code=ROLE_AGENT, removed_by=manager)

    assert not user_has_role(target, ROLE_AGENT)
    assert UserRole.objects.filter(user=target, role__code=ROLE_AGENT, is_active=False).exists()


def test_successful_canonical_removal_creates_role_removed_audit_event():
    manager = create_management_actor()
    target = create_user("audit-remove-target@example.test")
    assignment = assign_role(user=target, role_code=ROLE_AGENT, assigned_by=manager)
    before_count = AuditLog.objects.filter(action=ROLE_REMOVED).count()

    assert remove_role(user=target, role_code=ROLE_AGENT, removed_by=manager)
    log = AuditLog.objects.get(action=ROLE_REMOVED)

    assert before_count == 0
    assert log.actor == manager
    assert log.entity_type == "UserRole"
    assert log.entity_id == str(assignment.pk)
    assert log.before == {"user_id": str(target.pk), "role_code": ROLE_AGENT, "is_active": True}
    assert log.after == {"user_id": str(target.pk), "role_code": ROLE_AGENT, "is_active": False}


def test_failed_unauthorized_or_noop_removal_creates_no_success_audit():
    manager = create_management_actor()
    ordinary = create_user("audit-remove-ordinary@example.test")
    target = create_user("audit-remove-fail-target@example.test")
    assign_role(user=target, role_code=ROLE_AGENT, assigned_by=manager)

    with pytest.raises(PermissionDenied):
        remove_role(user=target, role_code=ROLE_AGENT, removed_by=ordinary)
    assert not remove_role(user=target, role_code=ROLE_OWNER, removed_by=manager)

    assert not AuditLog.objects.filter(action=ROLE_REMOVED).exists()
    assert user_has_role(target, ROLE_AGENT)


def test_removal_audit_failure_rolls_back_canonical_mutation():
    manager = create_management_actor()
    target = create_user("audit-remove-rollback@example.test")
    assign_role(user=target, role_code=ROLE_AGENT, assigned_by=manager)

    with patch("apps.roles.services.create_audit_log", side_effect=RuntimeError("audit failed")), pytest.raises(RuntimeError):
        remove_role(user=target, role_code=ROLE_AGENT, removed_by=manager)

    assert user_has_role(target, ROLE_AGENT)
    assert not AuditLog.objects.filter(action=ROLE_REMOVED).exists()


def test_role_audit_metadata_contains_no_sensitive_secrets():
    manager = create_management_actor()
    target = create_user("audit-secret-target@example.test")
    assign_role(user=target, role_code=ROLE_OWNER, assigned_by=manager)
    remove_role(user=target, role_code=ROLE_OWNER, removed_by=manager)
    metadata = " ".join(
        str(value)
        for log in AuditLog.objects.filter(action__in=[ROLE_ASSIGNED, ROLE_REMOVED])
        for value in [log.before, log.after]
    )

    assert "Strong-pass-482!" not in metadata
    assert "password" not in metadata.lower()
    assert "token" not in metadata.lower()
    assert "jwt" not in metadata.lower()
    assert "verification" not in metadata.lower()
    assert "reset" not in metadata.lower()


def test_unauthorized_actor_cannot_remove_canonical_role():
    manager = create_management_actor()
    actor = create_user("ordinary-remover@example.test")
    target = create_user("remove-denied-target@example.test")
    assign_role(user=target, role_code=ROLE_AGENT, assigned_by=manager)

    with pytest.raises(PermissionDenied):
        remove_role(user=target, role_code=ROLE_AGENT, removed_by=actor)
    assert user_has_role(target, ROLE_AGENT)


@pytest.mark.parametrize("operation", ["assign", "remove"])
def test_canonical_role_services_reject_unknown_role(operation):
    manager = create_management_actor(f"{operation}-unknown-manager@example.test")
    target = create_user(f"{operation}-unknown-target@example.test")

    with pytest.raises(ValidationError):
        if operation == "assign":
            assign_role(user=target, role_code="director", assigned_by=manager)
        else:
            remove_role(user=target, role_code="director", removed_by=manager)


def test_canonical_assignment_rejects_inactive_role():
    manager = create_management_actor()
    target = create_user("inactive-role-target@example.test")
    Role.objects.filter(code=ROLE_OWNER).update(is_active=False)

    with pytest.raises(ValidationError):
        assign_role(user=target, role_code=ROLE_OWNER, assigned_by=manager)
    assert not UserRole.objects.filter(user=target, role__code=ROLE_OWNER).exists()


def test_canonical_assignment_is_idempotent_and_records_actor():
    manager = create_management_actor()
    target = create_user("idempotent-assign-target@example.test")

    first = assign_role(user=target, role_code=ROLE_OWNER, assigned_by=manager)
    second = assign_role(user=target, role_code=ROLE_OWNER, assigned_by=manager)

    assert first.pk == second.pk
    assert second.assigned_by == manager
    assert UserRole.objects.filter(user=target, role__code=ROLE_OWNER, is_active=True).count() == 1


def test_canonical_removal_is_idempotent_and_stops_authorization():
    manager = create_management_actor()
    target = create_user("idempotent-remove-target@example.test")
    assign_role(user=target, role_code=ROLE_OWNER, assigned_by=manager)

    assert remove_role(user=target, role_code=ROLE_OWNER, removed_by=manager)
    assert not remove_role(user=target, role_code=ROLE_OWNER, removed_by=manager)

    assert not user_has_role(target, ROLE_OWNER)
    assert not IsLister().has_permission(request_for(target), view=None)


def test_inactive_assignment_does_not_authorize_after_service_removal():
    manager = create_management_actor()
    target = create_user("inactive-after-remove@example.test")
    assign_role(user=target, role_code=ROLE_AGENT, assigned_by=manager)
    remove_role(user=target, role_code=ROLE_AGENT, removed_by=manager)

    assert not user_has_role(target, ROLE_AGENT)
    assert not IsLister().has_permission(request_for(target), view=None)


@pytest.mark.parametrize("role_code", [ROLE_OWNER, ROLE_AGENT, ROLE_MANAGEMENT])
def test_ordinary_user_cannot_self_assign_privileged_canonical_roles(role_code):
    user = create_user(f"self-{role_code}@example.test")

    with pytest.raises(PermissionDenied):
        assign_role(user=user, role_code=role_code, assigned_by=user)
    assert not UserRole.objects.filter(user=user, role__code=role_code, is_active=True).exists()


def test_direct_service_call_cannot_bypass_management_authorization():
    manager = create_management_actor()
    target = create_user("bypass-target@example.test")
    UserRole.objects.filter(user=manager, role__code=ROLE_MANAGEMENT).update(is_active=False)

    with pytest.raises(PermissionDenied):
        assign_role(user=target, role_code=ROLE_OWNER, assigned_by=manager)


def test_registration_payload_cannot_inject_canonical_roles():
    response = api_client().post(
        "/api/v1/auth/register/",
        {
            "email": "inject-register@example.test",
            "phone": "+255799000001",
            "full_name": "Injected User",
            "password": "Strong-pass-482!",
            "role": ROLE_MANAGEMENT,
            "roles": [ROLE_OWNER],
        },
        format="json",
    )

    assert response.status_code == 201
    user = User.objects.get(email="inject-register@example.test")
    assert not UserRole.objects.filter(user=user).exists()
    assert not LegacyUserRole.objects.filter(user=user, role__code=ROLE_MANAGEMENT).exists()


def test_users_me_patch_cannot_inject_canonical_roles():
    user = create_user("inject-profile@example.test")

    response = api_client(user).patch(
        "/api/v1/users/me/",
        {"full_name": "Profile Updated", "roles": [ROLE_OWNER], "role": ROLE_MANAGEMENT},
        format="json",
    )
    user.refresh_from_db()

    assert response.status_code == 200
    assert user.full_name == "Profile Updated"
    assert not UserRole.objects.filter(user=user).exists()


def test_login_payload_cannot_inject_canonical_roles():
    user = create_user("inject-login@example.test")

    response = api_client().post(
        "/api/v1/auth/login/",
        {
            "email": user.email,
            "password": "Strong-pass-482!",
            "role": ROLE_MANAGEMENT,
            "roles": [ROLE_OWNER, ROLE_AGENT],
        },
        format="json",
    )

    assert response.status_code == 200
    assert not UserRole.objects.filter(user=user).exists()


def test_jwt_role_claims_do_not_authorize_canonical_permissions():
    user = create_user("jwt-claims@example.test")
    token = RefreshToken.for_user(user).access_token
    token["role"] = ROLE_MANAGEMENT
    token["roles"] = [ROLE_MANAGEMENT, ROLE_OWNER]
    raw_request = APIRequestFactory().get("/internal/", HTTP_AUTHORIZATION=f"Bearer {token}")
    authenticated_user, validated_token = JWTAuthentication().authenticate(raw_request)
    request = Request(raw_request)
    request.user = authenticated_user
    request.auth = validated_token

    assert not user_has_role(user, ROLE_MANAGEMENT)
    assert not IsManagement().has_permission(request, view=None)
    assert not IsLister().has_permission(request, view=None)


def test_account_serializers_do_not_expose_or_accept_roles():
    user = create_user("serializer-roles@example.test")

    assert "roles" not in UserPublicSerializer(user).data
    assert "roles" not in UserPrivateProfileSerializer(user).data
    assert "role" not in UserPublicSerializer(user).data
    assert "role" not in UserPrivateProfileSerializer(user).data
    assert "roles" not in UserPrivateProfileSerializer.Meta.fields
    assert "role" not in UserPrivateProfileSerializer.Meta.fields


@pytest.mark.parametrize("actor", [None, AnonymousUser()])
def test_unauthenticated_canonical_service_calls_are_denied(actor):
    target = create_user("unauth-service-target@example.test")

    with pytest.raises(PermissionDenied):
        assign_role(user=target, role_code=ROLE_OWNER, assigned_by=actor)
    with pytest.raises(PermissionDenied):
        remove_role(user=target, role_code=ROLE_OWNER, removed_by=actor)


def test_inactive_management_assignment_cannot_manage_canonical_roles():
    manager = create_management_actor()
    target = create_user("inactive-manager-assignment-target@example.test")
    UserRole.objects.filter(user=manager, role__code=ROLE_MANAGEMENT).update(is_active=False)

    with pytest.raises(PermissionDenied):
        assign_role(user=target, role_code=ROLE_OWNER, assigned_by=manager)
    with pytest.raises(PermissionDenied):
        remove_role(user=target, role_code=ROLE_OWNER, removed_by=manager)


def test_inactive_management_role_cannot_manage_canonical_roles():
    manager = create_management_actor()
    target = create_user("inactive-manager-role-target@example.test")
    Role.objects.filter(code=ROLE_MANAGEMENT).update(is_active=False)

    with pytest.raises(PermissionDenied):
        assign_role(user=target, role_code=ROLE_OWNER, assigned_by=manager)


def test_canonical_imports_and_app_labels_remain_stable():
    labels = [config.label for config in apps.get_app_configs()]

    assert len(labels) == len(set(labels))
    assert apps.get_app_config("roles").name == "apps.roles"
    assert apps.get_app_config("authorization").name == "apps.roles.legacy_authorization"
    assert apps.get_app_config("audit").name == "apps.audit.legacy_event_stream"
    assert callable(assign_role)
    assert callable(remove_role)
    assert callable(user_has_role)


def test_legacy_management_api_remains_on_legacy_authorization_store():
    manager = User.objects.create_superuser(
        email="legacy-manager@example.test",
        phone="+255799000002",
        full_name="Legacy Manager",
        password="Strong-pass-482!",
    )
    bootstrap_legacy_management(user=manager)
    target = User.objects.create_user(
        email="legacy-target@example.test",
        phone="+255799000003",
        full_name="Legacy Target",
        password="Strong-pass-482!",
        account_category="operational",
    )

    response = api_client(manager).post(
        f"/api/v1/management/authorization/users/{target.pk}/roles/assign/",
        {"role_code": "verifier"},
    )

    assert response.status_code == 200
    assert LegacyUserRole.objects.filter(user=target, role__code="verifier", is_active=True).exists()
    assert not UserRole.objects.filter(user=target, role__code="verifier").exists()
