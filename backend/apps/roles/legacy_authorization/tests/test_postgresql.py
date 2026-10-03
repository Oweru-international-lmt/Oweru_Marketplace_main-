"""Run with --ds=config.settings.test_postgresql on an isolated test database."""
import pytest
from django.db import connection, DatabaseError, transaction
from apps.audit.services import legacy_record_event


@pytest.mark.django_db
@pytest.mark.skipif(connection.vendor != "postgresql", reason="Requires PostgreSQL audit trigger")
@pytest.mark.parametrize("operation", ["UPDATE audit_auditevent SET action = 'rewritten' WHERE id = %s", "DELETE FROM audit_auditevent WHERE id = %s"])
def test_database_trigger_rejects_raw_audit_mutation(operation):
    event = legacy_record_event(action="test", entity_type="Test")
    with pytest.raises(DatabaseError, match="append-only"), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(operation, [event.pk])
    event.refresh_from_db()
    assert event.action == "test"


@pytest.mark.django_db
def test_authorization_database_constraints_and_index_exist():
    with connection.cursor() as cursor:
        assignments = connection.introspection.get_constraints(cursor, "authorization_userrole")
        grants = connection.introspection.get_constraints(cursor, "authorization_rolepermission")
        users = connection.introspection.get_constraints(cursor, "accounts_user")
    assert assignments["uniq_user_role"]["unique"]
    assert assignments["userrole_active_idx"]["index"]
    assert grants["uniq_role_permission"]["unique"]
    assert users["user_category_valid"]["check"]
