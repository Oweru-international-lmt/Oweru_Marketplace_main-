from django.db import migrations


def seed_canonical_roles(apps, schema_editor):
    from apps.roles.services import bootstrap_canonical_roles

    Role = apps.get_model("roles", "Role")
    bootstrap_canonical_roles(role_model=Role, using=schema_editor.connection.alias)


class Migration(migrations.Migration):
    dependencies = [
        ("roles", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_canonical_roles, migrations.RunPython.noop),
    ]
