from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_preferred_language"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="user",
            name="login_failures_max_five",
        ),
    ]
