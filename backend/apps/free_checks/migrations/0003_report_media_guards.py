from django.db import migrations


def install(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""
    CREATE FUNCTION free_check_guard_media() RETURNS trigger AS $$
    BEGIN
      IF EXISTS (SELECT 1 FROM free_checks_freecheckreport WHERE media_id=OLD.id)
      OR EXISTS (SELECT 1 FROM free_checks_freecheckphoto WHERE media_id=OLD.id)
      THEN RAISE EXCEPTION 'Free Check report and photo media are immutable'; END IF;
      IF TG_OP='DELETE' THEN RETURN OLD; END IF;
      RETURN NEW;
    END; $$ LANGUAGE plpgsql;
    CREATE TRIGGER free_check_private_media_lock BEFORE UPDATE OR DELETE ON media_media
    FOR EACH ROW EXECUTE FUNCTION free_check_guard_media();
    """)


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP TRIGGER free_check_private_media_lock ON media_media; DROP FUNCTION free_check_guard_media()")


class Migration(migrations.Migration):
    dependencies = [("free_checks", "0002_immutable_history")]
    operations = [migrations.RunPython(install, uninstall)]
