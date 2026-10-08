from django.db import migrations


def install(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""
    CREATE FUNCTION site_capture_guard_media() RETURNS trigger AS $$
    DECLARE media_uuid uuid;
    BEGIN
      IF TG_TABLE_NAME='media_mediavariant' THEN media_uuid=OLD.media_id; ELSE media_uuid=OLD.id; END IF;
      IF EXISTS (SELECT 1 FROM media_media m JOIN django_content_type ct ON ct.id=m.content_type_id JOIN site_capture_sitecapture c ON c.id=m.object_id WHERE m.id=media_uuid AND ct.app_label='site_capture' AND ct.model='sitecapture' AND c.status='SUBMITTED')
      OR EXISTS (SELECT 1 FROM verification_tasksubmission WHERE report_id=media_uuid)
      OR EXISTS (SELECT 1 FROM verification_verificationreport WHERE media_id=media_uuid)
      THEN RAISE EXCEPTION 'Submitted capture and evidence media cannot change'; END IF;
      IF TG_OP='DELETE' THEN RETURN OLD; END IF;
      RETURN NEW;
    END; $$ LANGUAGE plpgsql;
    CREATE TRIGGER capture_private_media_lock BEFORE UPDATE OR DELETE ON media_media FOR EACH ROW EXECUTE FUNCTION site_capture_guard_media();
    CREATE TRIGGER capture_private_variant_lock BEFORE UPDATE OR DELETE ON media_mediavariant FOR EACH ROW EXECUTE FUNCTION site_capture_guard_media();
    CREATE FUNCTION site_capture_guard_asset() RETURNS trigger AS $$
    DECLARE capture_uuid uuid;
    BEGIN
      IF TG_OP='INSERT' THEN capture_uuid=NEW.capture_id; ELSE capture_uuid=OLD.capture_id; END IF;
      IF TG_OP='UPDATE' OR EXISTS (SELECT 1 FROM site_capture_sitecapture WHERE id=capture_uuid AND status='SUBMITTED')
      THEN RAISE EXCEPTION 'Capture provenance is immutable after submission'; END IF;
      IF TG_OP='DELETE' THEN RETURN OLD; END IF;
      RETURN NEW;
    END; $$ LANGUAGE plpgsql;
    CREATE TRIGGER capture_asset_lock BEFORE INSERT OR UPDATE OR DELETE ON site_capture_captureasset FOR EACH ROW EXECUTE FUNCTION site_capture_guard_asset();
    """)


def uninstall(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("DROP TRIGGER IF EXISTS capture_private_media_lock ON media_media; DROP TRIGGER IF EXISTS capture_private_variant_lock ON media_mediavariant; DROP FUNCTION IF EXISTS site_capture_guard_media(); DROP TRIGGER IF EXISTS capture_asset_lock ON site_capture_captureasset; DROP FUNCTION IF EXISTS site_capture_guard_asset();")


class Migration(migrations.Migration):
    dependencies = [("site_capture", "0003_sitecapture_overlap_findings_captureasset_and_more"), ("verification", "0007_full_check_database_guards")]
    operations = [migrations.RunPython(install, uninstall)]
