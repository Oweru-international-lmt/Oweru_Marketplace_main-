from django.db import migrations


TABLES = [
    "verification_propertyverificationevidence", "verification_propertyrelationship",
    "verification_taskassignment", "verification_tasksubmission", "verification_jobhistory",
    "verification_fullcheckproof", "verification_fullcheckreceipt", "verification_ownerconsent",
    "verification_verificationresult", "verification_verificationreport",
]


def install(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""
        CREATE FUNCTION verification_reject_history_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'Submitted verification history is immutable'; END;
        $$ LANGUAGE plpgsql;
    """)
    for table in TABLES:
        schema_editor.execute(f'CREATE TRIGGER immutable_verification_history BEFORE UPDATE OR DELETE ON "{table}" FOR EACH ROW EXECUTE FUNCTION verification_reject_history_mutation()')
    schema_editor.execute("""
        CREATE FUNCTION verification_guard_capture() RETURNS trigger AS $$
        BEGIN
          IF TG_TABLE_NAME = 'site_capture_sitecapture' THEN
            IF OLD.status = 'SUBMITTED' THEN RAISE EXCEPTION 'Submitted capture is immutable'; END IF;
          ELSE
            IF EXISTS (SELECT 1 FROM site_capture_sitecapture WHERE id = COALESCE(NEW.capture_id, OLD.capture_id) AND status = 'SUBMITTED')
            THEN RAISE EXCEPTION 'Submitted corners are immutable'; END IF;
          END IF;
          IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER locked_capture BEFORE UPDATE OR DELETE ON site_capture_sitecapture FOR EACH ROW EXECUTE FUNCTION verification_guard_capture();
        CREATE TRIGGER locked_corner BEFORE INSERT OR UPDATE OR DELETE ON site_capture_capturecorner FOR EACH ROW EXECUTE FUNCTION verification_guard_capture();
    """)


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in TABLES:
        schema_editor.execute(f'DROP TRIGGER IF EXISTS immutable_verification_history ON "{table}"')
    schema_editor.execute("DROP FUNCTION IF EXISTS verification_reject_history_mutation()")
    schema_editor.execute("DROP TRIGGER IF EXISTS locked_capture ON site_capture_sitecapture")
    schema_editor.execute("DROP TRIGGER IF EXISTS locked_corner ON site_capture_capturecorner")
    schema_editor.execute("DROP FUNCTION IF EXISTS verification_guard_capture()")


class Migration(migrations.Migration):
    dependencies = [
        ("verification", "0004_propertyverificationevidence_author_role_and_more"),
        ("site_capture", "0002_sitecapture_area_difference_percent_and_more"),
    ]
    operations = [migrations.RunPython(install, uninstall)]
