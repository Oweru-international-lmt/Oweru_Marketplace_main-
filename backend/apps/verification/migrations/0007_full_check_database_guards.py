from django.db import migrations


def install(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""
    CREATE FUNCTION verification_guard_final_job() RETURNS trigger AS $$
    BEGIN
      IF TG_OP = 'UPDATE' AND (
        NEW.property_id IS DISTINCT FROM OLD.property_id OR NEW.buyer_id IS DISTINCT FROM OLD.buyer_id
        OR NEW.listing_id IS DISTINCT FROM OLD.listing_id OR NEW.fee IS DISTINCT FROM OLD.fee
        OR NEW.payment_reference IS DISTINCT FROM OLD.payment_reference OR NEW.kind IS DISTINCT FROM OLD.kind
        OR NEW.subject_snapshot IS DISTINCT FROM OLD.subject_snapshot OR NEW.scope_snapshot IS DISTINCT FROM OLD.scope_snapshot
      ) THEN RAISE EXCEPTION 'Full Check order context is frozen'; END IF;
      IF TG_OP='UPDATE' AND EXISTS (SELECT 1 FROM verification_ownerconsent WHERE job_id=OLD.id)
      AND (NEW.owner_user_id IS DISTINCT FROM OLD.owner_user_id OR NEW.owner_name IS DISTINCT FROM OLD.owner_name OR NEW.owner_phone IS DISTINCT FROM OLD.owner_phone)
      THEN RAISE EXCEPTION 'Consented owner context is frozen'; END IF;
      IF TG_OP = 'UPDATE' AND OLD.status IN ('PASSED','PROBLEM_FOUND','NOT_COMPLETED') AND NEW.status IS DISTINCT FROM OLD.status
      THEN RAISE EXCEPTION 'Final Full Check status is immutable'; END IF;
      IF NEW.status = 'PASSED' AND NEW.invalidated_at IS NULL THEN
        IF NOT EXISTS (SELECT 1 FROM verification_fullcheckreceipt WHERE job_id=NEW.id AND amount=NEW.fee)
        OR NOT EXISTS (SELECT 1 FROM verification_ownerconsent WHERE job_id=NEW.id AND decision='CONFIRM')
        OR NOT EXISTS (SELECT 1 FROM verification_verificationresult WHERE job_id=NEW.id AND result='PASSED' AND verifier_id=NEW.verifier_id)
        OR NOT EXISTS (SELECT 1 FROM verification_verificationreport WHERE job_id=NEW.id)
        OR EXISTS (SELECT 1 FROM verification_verificationjob WHERE property_id=NEW.property_id AND status='PROBLEM_FOUND' AND invalidated_at IS NULL AND id<>NEW.id)
        OR EXISTS (SELECT 1 FROM verification_verificationtask WHERE job_id=NEW.id AND required AND status<>'SUBMITTED')
        OR NOT EXISTS (SELECT 1 FROM verification_verificationtask WHERE job_id=NEW.id AND kind='LOCAL_OFFICE' AND status='SUBMITTED')
        OR NOT EXISTS (SELECT 1 FROM verification_tasksubmission s JOIN verification_verificationtask t ON t.id=s.task_id JOIN site_capture_sitecapture c ON c.id=s.capture_id WHERE t.job_id=NEW.id AND (t.kind='SITE_CAPTURE' OR t.professional_type='SURVEYOR') AND c.status='SUBMITTED' AND c.measured_area_sqm>0 AND c.observed_boundary IS NOT NULL AND (SELECT COUNT(*) FROM site_capture_capturecorner WHERE capture_id=c.id)>=3)
        OR EXISTS (SELECT 1 FROM properties_propertyrecord p WHERE p.id=NEW.property_id AND p.title_type='REGISTERED_TITLE' AND NOT EXISTS (SELECT 1 FROM verification_verificationtask WHERE job_id=NEW.id AND kind='REGISTRY' AND status='SUBMITTED'))
        THEN RAISE EXCEPTION 'Full Check completion prerequisites are missing'; END IF;
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    CREATE TRIGGER full_check_prerequisites BEFORE INSERT OR UPDATE ON verification_verificationjob FOR EACH ROW EXECUTE FUNCTION verification_guard_final_job();

    CREATE FUNCTION verification_guard_submission() RETURNS trigger AS $$
    DECLARE t verification_verificationtask; j verification_verificationjob;
    BEGIN
      SELECT * INTO t FROM verification_verificationtask WHERE id=NEW.task_id;
      SELECT * INTO j FROM verification_verificationjob WHERE id=t.job_id;
      IF j.status<>'IN_PROGRESS' OR j.invalidated_at IS NOT NULL OR t.status NOT IN ('ASSIGNED','ACCEPTED')
      OR NOT EXISTS (SELECT 1 FROM verification_fullcheckreceipt WHERE job_id=j.id)
      OR NOT EXISTS (SELECT 1 FROM verification_ownerconsent WHERE job_id=j.id AND decision='CONFIRM')
      THEN RAISE EXCEPTION 'Task is not open for submission'; END IF;
      IF t.kind='LOCAL_OFFICE' AND (NOT NEW.signed_and_stamped OR NEW.report_id IS NULL OR NOT (NEW.findings ?& ARRAY['1','2','3','4','5']))
      THEN RAISE EXCEPTION 'Five answers and signed stamped evidence are required'; END IF;
      IF t.kind='PROFESSIONAL' AND (t.status<>'ACCEPTED' OR t.assignee_id IS DISTINCT FROM NEW.author_id)
      THEN RAISE EXCEPTION 'Only the accepted Professional may submit'; END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    CREATE TRIGGER verification_submission_prerequisites BEFORE INSERT ON verification_tasksubmission FOR EACH ROW EXECUTE FUNCTION verification_guard_submission();

    CREATE FUNCTION verification_guard_evidence_media() RETURNS trigger AS $$
    BEGIN
      IF EXISTS (SELECT 1 FROM verification_tasksubmission WHERE report_id=OLD.id)
      OR EXISTS (SELECT 1 FROM verification_verificationreport WHERE media_id=OLD.id)
      OR EXISTS (SELECT 1 FROM verification_fullcheckproof WHERE media_id=OLD.id)
      OR EXISTS (SELECT 1 FROM verification_fullcheckreceipt WHERE tax_receipt_id=OLD.id)
      THEN RAISE EXCEPTION 'Submitted verification media is immutable'; END IF;
      IF TG_OP='DELETE' THEN RETURN OLD; END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    CREATE TRIGGER verification_private_media_lock BEFORE UPDATE OR DELETE ON media_media FOR EACH ROW EXECUTE FUNCTION verification_guard_evidence_media();
    """)


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("DROP TRIGGER IF EXISTS full_check_prerequisites ON verification_verificationjob; DROP FUNCTION IF EXISTS verification_guard_final_job(); DROP TRIGGER IF EXISTS verification_submission_prerequisites ON verification_tasksubmission; DROP FUNCTION IF EXISTS verification_guard_submission(); DROP TRIGGER IF EXISTS verification_private_media_lock ON media_media; DROP FUNCTION IF EXISTS verification_guard_evidence_media();")


class Migration(migrations.Migration):
    dependencies = [("verification", "0006_tasksubmission_signed_and_stamped_and_more")]
    operations = [migrations.RunPython(install, uninstall)]
