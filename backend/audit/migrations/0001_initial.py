import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import uuid


def install_append_only_trigger(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""
        CREATE FUNCTION audit_event_reject_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit events are append-only';
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER audit_event_append_only
        BEFORE UPDATE OR DELETE ON audit_auditevent
        FOR EACH ROW EXECUTE FUNCTION audit_event_reject_mutation();
    """)


def remove_append_only_trigger(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("DROP TRIGGER IF EXISTS audit_event_append_only ON audit_auditevent; DROP FUNCTION IF EXISTS audit_event_reject_mutation();")


class Migration(migrations.Migration):
    initial = True
    dependencies = [("accounts", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("action", models.CharField(max_length=100)),
                ("entity_type", models.CharField(max_length=100)),
                ("entity_id", models.CharField(blank=True, max_length=100)),
                ("before_state", models.JSONField(blank=True, default=dict)),
                ("after_state", models.JSONField(blank=True, default=dict)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="audit_events", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(model_name="auditevent", index=models.Index(fields=["entity_type", "entity_id"], name="audit_entity_idx")),
        migrations.AddIndex(model_name="auditevent", index=models.Index(fields=["actor", "created_at"], name="audit_actor_time_idx")),
        migrations.AddIndex(model_name="auditevent", index=models.Index(fields=["action", "created_at"], name="audit_action_time_idx")),
        migrations.RunPython(install_append_only_trigger, remove_append_only_trigger),
    ]
