from django.db import migrations


def install(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""CREATE FUNCTION notification_history_guard() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'Notification delivery history is immutable'; END; $$ LANGUAGE plpgsql;
    CREATE TRIGGER notification_delivery_history BEFORE UPDATE OR DELETE ON notifications_deliveryattempt FOR EACH ROW EXECUTE FUNCTION notification_history_guard();
    CREATE TRIGGER notification_template_history BEFORE UPDATE OR DELETE ON notifications_templatehistory FOR EACH ROW EXECUTE FUNCTION notification_history_guard();""")


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP TRIGGER notification_delivery_history ON notifications_deliveryattempt; DROP TRIGGER notification_template_history ON notifications_templatehistory; DROP FUNCTION notification_history_guard()")


class Migration(migrations.Migration):
    dependencies = [("notifications", "0001_initial")]
    operations = [migrations.RunPython(install, uninstall)]
