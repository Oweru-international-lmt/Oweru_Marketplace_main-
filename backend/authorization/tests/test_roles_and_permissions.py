import pytest
from django.db import IntegrityError, transaction
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from accounts.models import User
from authorization.models import Permission, Role, RolePermission, UserRole
from authorization.permissions import HasMarketplacePermission, HasMarketplaceRole, IsManagement, IsSelf
from authorization.services import assign_role, bootstrap_management


pytestmark = pytest.mark.django_db


@pytest.fixture
def management_actor():
    actor = User.objects.create_superuser(email="manager@example.test", phone="+255700000001", full_name="Manager", password="Strong-pass-482!")
    bootstrap_management(user=actor)
    return actor


class RoleView(APIView):
    permission_classes = [IsAuthenticated, HasMarketplaceRole]
    required_role = "verifier"


class PermissionView(APIView):
    permission_classes = [IsAuthenticated, HasMarketplacePermission]
    required_marketplace_permission = "verification.review"


def test_expected_role_catalog_is_seeded():
    assert set(Role.objects.values_list("code", flat=True)) == {
        "buyer", "owner", "agent", "local_official", "professional", "verifier", "marketer", "management"
    }


def test_role_permission_and_user_role_relationships_enforce_uniqueness():
    user = User.objects.create_user(email="asha@example.test", phone="+255700123456", full_name="Asha", password="Strong-pass-482!")
    role = Role.objects.get(code="verifier")
    permission = Permission.objects.create(code="verification.review", name="Review verification")
    RolePermission.objects.create(role=role, permission=permission)
    UserRole.objects.create(user=user, role=role)
    with pytest.raises(IntegrityError), transaction.atomic():
        RolePermission.objects.create(role=role, permission=permission)
    with pytest.raises(IntegrityError), transaction.atomic():
        UserRole.objects.create(user=user, role=role)


def test_server_side_role_and_database_permission_checks(management_actor):
    user = User.objects.create_user(email="asha@example.test", phone="+255700123456", full_name="Asha", password="Strong-pass-482!", account_category="operational")
    role = Role.objects.get(code="verifier")
    permission = Permission.objects.create(code="verification.review", name="Review verification")
    RolePermission.objects.create(role=role, permission=permission)
    raw_request = APIRequestFactory().get("/")
    force_authenticate(raw_request, user=user)
    request = Request(raw_request)
    assert not HasMarketplaceRole().has_permission(request, RoleView())
    assert not HasMarketplacePermission().has_permission(request, PermissionView())
    assign_role(user=user, role_code="verifier", assigned_by=management_actor)
    raw_request = APIRequestFactory().get("/")
    force_authenticate(raw_request, user=user)
    request = Request(raw_request)
    assert HasMarketplaceRole().has_permission(request, RoleView())
    assert HasMarketplacePermission().has_permission(request, PermissionView())


def test_management_permission_requires_management_role():
    user = User.objects.create_superuser(email="asha@example.test", phone="+255700123456", full_name="Asha", password="Strong-pass-482!")
    raw_request = APIRequestFactory().get("/")
    force_authenticate(raw_request, user=user)
    request = Request(raw_request)
    view = APIView()
    assert not IsManagement().has_permission(request, view)
    bootstrap_management(user=user)
    raw_request = APIRequestFactory().get("/")
    force_authenticate(raw_request, user=user)
    request = Request(raw_request)
    assert IsManagement().has_permission(request, view)


def test_self_object_permission_denies_other_users():
    user = User.objects.create_user(email="asha@example.test", phone="+255700123456", full_name="Asha", password="Strong-pass-482!")
    other = User.objects.create_user(email="juma@example.test", phone="+255700123457", full_name="Juma", password="Strong-pass-482!")
    raw_request = APIRequestFactory().get("/")
    force_authenticate(raw_request, user=user)
    request = Request(raw_request)
    assert IsSelf().has_object_permission(request, None, user)
    assert not IsSelf().has_object_permission(request, None, other)
