from django.db import migrations, models


def classify_accounts(apps, schema_editor):
    alias = schema_editor.connection.alias
    User = apps.get_model("accounts", "User")
    UserRole = apps.get_model("authorization", "UserRole")
    public = {"buyer", "owner", "agent"}
    for user in User.objects.using(alias).all().iterator():
        # Include revoked history: revocation must not silently convert categories.
        codes = set(UserRole.objects.using(alias).filter(user_id=user.pk).values_list("role__code", flat=True))
        operational = bool(codes - public) or user.is_staff or user.is_superuser
        if operational and codes & public:
            raise RuntimeError(f"Mixed public/operational account requires review before migration: {user.pk}")
        User.objects.using(alias).filter(pk=user.pk).update(account_category="operational" if operational else "public")


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_email_sign_in"), ("authorization", "0001_initial")]
    operations = [
        migrations.AddField(model_name="user", name="account_category", field=models.CharField(choices=[("public", "Public"), ("operational", "Operational")], default="public", editable=False, max_length=12)),
        migrations.RunPython(classify_accounts, migrations.RunPython.noop),
        migrations.AddConstraint(model_name="user", constraint=models.CheckConstraint(condition=models.Q(account_category__in=["public", "operational"]), name="user_category_valid")),
    ]
