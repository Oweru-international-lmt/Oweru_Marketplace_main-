from django.db import migrations


def install(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""
    CREATE FUNCTION complaint_guard_media() RETURNS trigger AS $$
    BEGIN
      IF EXISTS (SELECT 1 FROM complaints_complaintevidence WHERE media_id=OLD.id)
      THEN RAISE EXCEPTION 'Complaint evidence media is immutable'; END IF;
      IF TG_OP='DELETE' THEN RETURN OLD; END IF;
      RETURN NEW;
    END; $$ LANGUAGE plpgsql;
    CREATE TRIGGER complaint_private_media_lock BEFORE UPDATE OR DELETE ON media_media
    FOR EACH ROW EXECUTE FUNCTION complaint_guard_media();
    """)


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP TRIGGER complaint_private_media_lock ON media_media; DROP FUNCTION complaint_guard_media()")


class Migration(migrations.Migration):
    dependencies = [("complaints", "0002_history_guards")]
    operations = [migrations.RunPython(install, uninstall)]
