from django.db import migrations

TABLES = ["free_checks_freecheck", "free_checks_freechecklead", "free_checks_freecheckphoto", "free_checks_freecheckreport"]


def install(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("CREATE FUNCTION free_check_reject_mutation() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'Free Check history is immutable'; END; $$ LANGUAGE plpgsql")
    for table in TABLES:
        schema_editor.execute(f'CREATE TRIGGER free_check_history BEFORE UPDATE OR DELETE ON "{table}" FOR EACH ROW EXECUTE FUNCTION free_check_reject_mutation()')


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        for table in TABLES:
            schema_editor.execute(f'DROP TRIGGER free_check_history ON "{table}"')
        schema_editor.execute("DROP FUNCTION free_check_reject_mutation()")


class Migration(migrations.Migration):
    dependencies = [("free_checks", "0001_initial"), ("properties", "0003_propertyrecord_is_outside_check_and_more")]
    operations = [migrations.RunPython(install, uninstall)]
