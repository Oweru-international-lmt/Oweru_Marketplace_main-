import uuid

import django.contrib.auth.validators
import django.utils.timezone
from django.db import migrations, models
from django.db.models import Q
import django.db.models.deletion
import apps.accounts.managers


class Migration(migrations.Migration):
    initial = True

    dependencies = [("auth", "0012_alter_user_first_name_max_length")]

    operations = [
        migrations.CreateModel(
            name="User",
            fields=[
                ("password", models.CharField(max_length=128, verbose_name="password")),
                ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
                ("is_superuser", models.BooleanField(default=False, help_text="Designates that this user has all permissions without explicitly assigning them.", verbose_name="superuser status")),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("phone", models.CharField(max_length=30, unique=True)),
                ("full_name", models.CharField(max_length=255)),
                ("email", models.EmailField(blank=True, max_length=254, null=True)),
                ("language", models.CharField(choices=[("en", "English"), ("sw", "Kiswahili")], default="sw", max_length=2)),
                ("is_active", models.BooleanField(default=True)),
                ("is_staff", models.BooleanField(default=False)),
                ("failed_login_attempts", models.PositiveSmallIntegerField(default=0, editable=False)),
                ("locked_until", models.DateTimeField(blank=True, editable=False, null=True)),
                ("date_joined", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("groups", models.ManyToManyField(blank=True, help_text="The groups this user belongs to. A user will get all permissions granted to each of their groups.", related_name="user_set", related_query_name="user", to="auth.group", verbose_name="groups")),
                ("user_permissions", models.ManyToManyField(blank=True, help_text="Specific permissions for this user.", related_name="user_set", related_query_name="user", to="auth.permission", verbose_name="user permissions")),
            ],
            options={"ordering": ["-created_at"]},
            managers=[("objects", apps.accounts.managers.UserManager())],
        ),
        migrations.CreateModel(
            name="SensitiveConfirmation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("purpose", models.CharField(max_length=64)),
                ("subject_type", models.CharField(blank=True, max_length=100)),
                ("subject_id", models.CharField(blank=True, max_length=100)),
                ("token_digest", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sensitive_confirmations", to="accounts.user")),
            ],
        ),
        migrations.AddConstraint(model_name="user", constraint=models.CheckConstraint(condition=~Q(phone=""), name="user_phone_not_blank")),
        migrations.AddConstraint(model_name="user", constraint=models.CheckConstraint(condition=Q(language__in=["en", "sw"]), name="user_language_supported")),
        migrations.AddConstraint(model_name="user", constraint=models.CheckConstraint(condition=Q(failed_login_attempts__lte=5), name="login_failures_max_five")),
        migrations.AddIndex(model_name="sensitiveconfirmation", index=models.Index(fields=["user", "purpose", "expires_at"], name="confirm_user_purp_idx")),
        migrations.AddIndex(model_name="sensitiveconfirmation", index=models.Index(fields=["subject_type", "subject_id"], name="confirm_subject_idx")),
    ]
