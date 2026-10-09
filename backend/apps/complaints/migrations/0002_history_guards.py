from django.db import migrations

TABLES = ["complaints_complainthistory", "complaints_complaintresponse", "complaints_complaintevidence"]


def install(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("CREATE FUNCTION complaint_reject_history_mutation() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'Complaint evidence and history are immutable'; END; $$ LANGUAGE plpgsql")
    for table in TABLES:
        schema_editor.execute(f'CREATE TRIGGER complaint_history BEFORE UPDATE OR DELETE ON "{table}" FOR EACH ROW EXECUTE FUNCTION complaint_reject_history_mutation()')
    schema_editor.execute("""CREATE FUNCTION complaint_guard_lifecycle() RETURNS trigger AS $$
    BEGIN
      IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Complaints cannot be deleted'; END IF;
      IF NEW.name IS DISTINCT FROM OLD.name OR NEW.phone IS DISTINCT FROM OLD.phone OR NEW.description IS DISTINCT FROM OLD.description OR NEW.category IS DISTINCT FROM OLD.category OR NEW.deal_id IS DISTINCT FROM OLD.deal_id OR NEW.property_id IS DISTINCT FROM OLD.property_id OR NEW.source IS DISTINCT FROM OLD.source THEN RAISE EXCEPTION 'Complaint intake is immutable'; END IF;
      IF NEW.version <> OLD.version + 1 THEN RAISE EXCEPTION 'Complaint version must advance once'; END IF;
      IF NEW.status <> OLD.status AND NOT (
        OLD.status='RECEIVED' AND NEW.status='IN_REVIEW' OR
        OLD.status='IN_REVIEW' AND NEW.status IN ('WAITING_INFORMATION','RESOLVED') OR
        OLD.status='WAITING_INFORMATION' AND NEW.status IN ('IN_REVIEW','RESOLVED') OR
        OLD.status IN ('RESOLVED','CLOSED') AND NEW.status='UNDER_FINAL_REVIEW' AND OLD.final_review_requested_at IS NULL OR
        OLD.status IN ('RESOLVED','UNDER_FINAL_REVIEW') AND NEW.status='CLOSED'
      ) THEN RAISE EXCEPTION 'Invalid complaint transition'; END IF;
      RETURN NEW;
    END; $$ LANGUAGE plpgsql;
    CREATE TRIGGER complaint_lifecycle BEFORE UPDATE OR DELETE ON complaints_complaint FOR EACH ROW EXECUTE FUNCTION complaint_guard_lifecycle();""")


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        for table in TABLES:
            schema_editor.execute(f'DROP TRIGGER complaint_history ON "{table}"')
        schema_editor.execute("DROP TRIGGER complaint_lifecycle ON complaints_complaint; DROP FUNCTION complaint_guard_lifecycle(); DROP FUNCTION complaint_reject_history_mutation()")


class Migration(migrations.Migration):
    dependencies = [("complaints", "0001_initial")]
    operations = [migrations.RunPython(install, uninstall)]
