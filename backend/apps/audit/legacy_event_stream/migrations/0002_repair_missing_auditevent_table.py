from django.db import migrations


def ensure_audit_event_table(apps, schema_editor):
    table_name = "audit_auditevent"
    legacy_table_name = "audit_auditlog"
    quote_name = schema_editor.quote_name

    with schema_editor.connection.cursor() as cursor:
        table_names = set(schema_editor.connection.introspection.table_names(cursor))

    if table_name not in table_names and legacy_table_name in table_names:
        schema_editor.execute(f"ALTER TABLE {quote_name(legacy_table_name)} RENAME TO {quote_name(table_name)}")
        with schema_editor.connection.cursor() as cursor:
            columns = {
                column.name
                for column in schema_editor.connection.introspection.get_table_description(cursor, table_name)
            }
        if "before" in columns and "before_state" not in columns:
            schema_editor.execute(
                f"ALTER TABLE {quote_name(table_name)} "
                f"RENAME COLUMN {quote_name('before')} TO {quote_name('before_state')}"
            )
        if "after" in columns and "after_state" not in columns:
            schema_editor.execute(
                f"ALTER TABLE {quote_name(table_name)} "
                f"RENAME COLUMN {quote_name('after')} TO {quote_name('after_state')}"
            )
        if "updated_at" not in columns:
            schema_editor.execute(
                f"ALTER TABLE {quote_name(table_name)} "
                "ADD COLUMN updated_at timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP"
            )
            schema_editor.execute(
                f"ALTER TABLE {quote_name(table_name)} ALTER COLUMN updated_at DROP DEFAULT"
            )

    with schema_editor.connection.cursor() as cursor:
        table_names = set(schema_editor.connection.introspection.table_names(cursor))

    if table_name not in table_names:
        schema_editor.execute("""
            CREATE TABLE IF NOT EXISTS audit_auditevent (
                id uuid NOT NULL PRIMARY KEY,
                created_at timestamp with time zone NOT NULL,
                updated_at timestamp with time zone NOT NULL,
                action varchar(100) NOT NULL,
                entity_type varchar(100) NOT NULL,
                entity_id varchar(100) NOT NULL,
                before_state jsonb NOT NULL,
                after_state jsonb NOT NULL,
                ip_address inet NULL,
                user_agent text NOT NULL,
                actor_id uuid NULL REFERENCES accounts_user(id) DEFERRABLE INITIALLY DEFERRED
            );
            CREATE INDEX IF NOT EXISTS audit_auditevent_created_at_58e81936 ON audit_auditevent (created_at);
            CREATE INDEX IF NOT EXISTS audit_auditevent_actor_id_270bb4b7 ON audit_auditevent (actor_id);
            CREATE INDEX IF NOT EXISTS audit_entity_idx ON audit_auditevent (entity_type, entity_id);
            CREATE INDEX IF NOT EXISTS audit_actor_time_idx ON audit_auditevent (actor_id, created_at);
            CREATE INDEX IF NOT EXISTS audit_action_time_idx ON audit_auditevent (action, created_at);
        """)

    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("""
            CREATE OR REPLACE FUNCTION audit_event_reject_mutation() RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'audit events are append-only';
            END;
            $$ LANGUAGE plpgsql;
            DROP TRIGGER IF EXISTS audit_event_append_only ON audit_auditevent;
            CREATE TRIGGER audit_event_append_only
            BEFORE UPDATE OR DELETE ON audit_auditevent
            FOR EACH ROW EXECUTE FUNCTION audit_event_reject_mutation();
        """)


class Migration(migrations.Migration):
    dependencies = [("audit", "0001_initial")]
    operations = [migrations.RunPython(ensure_audit_event_table, migrations.RunPython.noop)]
