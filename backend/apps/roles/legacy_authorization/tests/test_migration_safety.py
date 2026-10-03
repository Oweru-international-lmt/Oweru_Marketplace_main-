from importlib import import_module
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from apps.accounts.models import User
from apps.roles.legacy_authorization.models import Role, UserRole, Permission, RolePermission

pytestmark = pytest.mark.django_db


def test_category_backfill_classifies_history_and_roleless_accounts():
    user = User.objects.create_user(email="history@test.test", phone="201", full_name="History", password="Strong-pass-482!")
    UserRole.objects.create(user=user, role=Role.objects.get(code="professional"), is_active=False)
    public = User.objects.create_user(email="public@test.test", phone="202", full_name="Public", password="Strong-pass-482!")
    module = import_module("apps.accounts.migrations.0003_account_category")
    module.classify_accounts(apps, SimpleNamespace(connection=connection))
    user.refresh_from_db()
    public.refresh_from_db()
    assert user.account_category == "operational"
    assert public.account_category == "public"


def test_category_backfill_rejects_mixed_history():
    user = User.objects.create_user(email="mixed@test.test", phone="203", full_name="Mixed", password="Strong-pass-482!")
    for code in ("buyer", "verifier"):
        UserRole.objects.create(user=user, role=Role.objects.get(code=code), is_active=False)
    with pytest.raises(RuntimeError, match="Mixed public/operational"):
        import_module("apps.accounts.migrations.0003_account_category").classify_accounts(apps, SimpleNamespace(connection=connection))


def test_seed_refuses_noncanonical_existing_grants():
    permission = Permission.objects.get(code="payment.confirm")
    RolePermission.objects.create(role=Role.objects.get(code="buyer"), permission=permission)
    with pytest.raises(RuntimeError, match="noncanonical grants"):
        import_module("apps.roles.legacy_authorization.migrations.0002_permission_catalog").seed_catalog(apps, SimpleNamespace(connection=connection))


def test_migration_graph_has_no_unapplied_nodes_in_test_database():
    executor = MigrationExecutor(connection)
    assert executor.migration_plan(executor.loader.graph.leaf_nodes()) == []
