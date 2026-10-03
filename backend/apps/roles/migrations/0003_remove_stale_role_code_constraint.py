from django.db import migrations


def drop_stale_role_code_constraint(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("ALTER TABLE roles_role DROP CONSTRAINT IF EXISTS roles_role_code_valid")


class Migration(migrations.Migration):
    dependencies = [
        ("roles", "0001_initial"),
    ]

    run_before = [
        ("roles", "0002_seed_canonical_roles"),
    ]

    operations = [
        migrations.RunPython(drop_stale_role_code_constraint, migrations.RunPython.noop),
    ]
