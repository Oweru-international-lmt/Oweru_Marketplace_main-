from django.db import migrations


def install(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("""CREATE FUNCTION administration_history_guard() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'Administration history is immutable'; END; $$ LANGUAGE plpgsql;
        CREATE TRIGGER administration_history BEFORE UPDATE OR DELETE ON administration_administrationhistory FOR EACH ROW EXECUTE FUNCTION administration_history_guard();
        CREATE TRIGGER settings_history BEFORE UPDATE OR DELETE ON verification_settinghistory FOR EACH ROW EXECUTE FUNCTION administration_history_guard();""")


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP TRIGGER administration_history ON administration_administrationhistory; DROP TRIGGER settings_history ON verification_settinghistory; DROP FUNCTION administration_history_guard()")


class Migration(migrations.Migration):
    dependencies = [("administration", "0001_initial"), ("verification", "0010_verificationsetting_version_settinghistory")]
    operations = [migrations.RunPython(install, uninstall)]
