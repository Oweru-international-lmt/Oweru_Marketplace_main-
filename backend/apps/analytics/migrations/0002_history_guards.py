from django.db import migrations


def install(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("""CREATE FUNCTION analytics_history_guard() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'Analytics facts are immutable'; END; $$ LANGUAGE plpgsql;
        CREATE TRIGGER market_event_history BEFORE UPDATE OR DELETE ON analytics_marketevent FOR EACH ROW EXECUTE FUNCTION analytics_history_guard();
        CREATE TRIGGER market_lead_source_history BEFORE UPDATE OR DELETE ON analytics_leadattribution FOR EACH ROW EXECUTE FUNCTION analytics_history_guard();
        CREATE TRIGGER market_deal_price_history BEFORE UPDATE OR DELETE ON analytics_dealpricesnapshot FOR EACH ROW EXECUTE FUNCTION analytics_history_guard();""")


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP TRIGGER market_event_history ON analytics_marketevent; DROP TRIGGER market_lead_source_history ON analytics_leadattribution; DROP TRIGGER market_deal_price_history ON analytics_dealpricesnapshot; DROP FUNCTION analytics_history_guard()")


class Migration(migrations.Migration):
    dependencies = [("analytics", "0001_initial")]
    operations = [migrations.RunPython(install, uninstall)]
