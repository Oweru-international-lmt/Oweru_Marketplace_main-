from django.db import migrations


def install(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("""CREATE FUNCTION marketing_history_guard() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'Marketing history is immutable'; END; $$ LANGUAGE plpgsql;
        CREATE TRIGGER marketing_consent_history BEFORE UPDATE OR DELETE ON marketing_consenthistory FOR EACH ROW EXECUTE FUNCTION marketing_history_guard();
        CREATE TRIGGER marketing_campaign_history BEFORE UPDATE OR DELETE ON marketing_campaign FOR EACH ROW EXECUTE FUNCTION marketing_history_guard();
        CREATE TRIGGER marketing_attempt_history BEFORE UPDATE OR DELETE ON marketing_campaignattempt FOR EACH ROW EXECUTE FUNCTION marketing_history_guard();""")


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP TRIGGER marketing_consent_history ON marketing_consenthistory; DROP TRIGGER marketing_campaign_history ON marketing_campaign; DROP TRIGGER marketing_attempt_history ON marketing_campaignattempt; DROP FUNCTION marketing_history_guard()")


class Migration(migrations.Migration):
    dependencies = [("marketing", "0001_initial")]
    operations = [migrations.RunPython(install, uninstall)]
