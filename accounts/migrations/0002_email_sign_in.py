from django.db import migrations, models
from django.db.models import Q


def lowercase_and_check_emails(apps, schema_editor):
    """Email becomes the required, unique sign-in identifier.

    Existing emails are lowercased. Accounts without an email, or two accounts
    sharing one address, cannot be fixed automatically, so the migration stops
    and lists them instead of inventing data.
    """
    User = apps.get_model("accounts", "User")
    missing = list(User.objects.filter(Q(email__isnull=True) | Q(email="")).values_list("phone", flat=True))
    if missing:
        raise RuntimeError(f"Add an email address to these accounts before migrating: {', '.join(missing)}")

    seen = {}
    for user in User.objects.all().only("id", "email", "phone"):
        normalized = user.email.strip().lower()
        if normalized in seen:
            raise RuntimeError(f"Accounts {seen[normalized]} and {user.phone} share the email {normalized}.")
        seen[normalized] = user.phone
        if user.email != normalized:
            User.objects.filter(pk=user.pk).update(email=normalized)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]

    operations = [
        migrations.RunPython(lowercase_and_check_emails, migrations.RunPython.noop),
        migrations.AlterField(model_name="user", name="email", field=models.EmailField(max_length=254, unique=True)),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(condition=~Q(email=""), name="user_email_not_blank"),
        ),
    ]
