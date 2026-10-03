from django.db import migrations, models


def drop_old_language_constraint(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("ALTER TABLE accounts_user DROP CONSTRAINT IF EXISTS user_language_supported")


def restore_old_language_constraint(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        "ALTER TABLE accounts_user "
        "ADD CONSTRAINT user_language_supported CHECK (preferred_language IN ('en', 'sw'))"
    )


def ensure_preferred_language_constraint(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'user_preferred_language_supported'
                  AND conrelid = 'accounts_user'::regclass
            ) THEN
                ALTER TABLE accounts_user
                ADD CONSTRAINT user_preferred_language_supported
                CHECK (preferred_language IN ('en', 'sw'));
            END IF;
        END $$;
    """)


def drop_preferred_language_constraint(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("ALTER TABLE accounts_user DROP CONSTRAINT IF EXISTS user_preferred_language_supported")


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_account_category")]

    operations = [
        migrations.RenameField(
            model_name="user",
            old_name="language",
            new_name="preferred_language",
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(drop_old_language_constraint, restore_old_language_constraint)
            ],
            state_operations=[
                migrations.RemoveConstraint(
                    model_name="user",
                    name="user_language_supported",
                )
            ],
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(ensure_preferred_language_constraint, drop_preferred_language_constraint)
            ],
            state_operations=[
                migrations.AddConstraint(
                    model_name="user",
                    constraint=models.CheckConstraint(
                        condition=models.Q(preferred_language__in=["en", "sw"]),
                        name="user_preferred_language_supported",
                    ),
                )
            ],
        ),
    ]
