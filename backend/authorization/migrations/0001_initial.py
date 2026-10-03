from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
import django.db.models.deletion
import uuid


def seed_roles(apps, schema_editor):
    Role = apps.get_model("authorization", "Role")
    names = (
        ("buyer", "Buyer"),
        ("owner", "Owner"),
        ("agent", "Agent"),
        ("local_official", "Local official"),
        ("professional", "Professional"),
        ("verifier", "Verifier"),
        ("marketer", "Marketer"),
        ("management", "Management"),
    )
    for code, name in names:
        Role.objects.using(schema_editor.connection.alias).get_or_create(code=code, defaults={"name": name})


class Migration(migrations.Migration):
    initial = True
    dependencies = [("accounts", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="Role",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(choices=[("buyer", "Buyer"), ("owner", "Owner"), ("agent", "Agent"), ("local_official", "Local official"), ("professional", "Professional"), ("verifier", "Verifier"), ("marketer", "Marketer"), ("management", "Management")], max_length=30, unique=True)),
                ("name", models.CharField(max_length=100)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["code"]},
        ),
        migrations.AddConstraint(model_name="role", constraint=models.CheckConstraint(condition=Q(code__in=["buyer", "owner", "agent", "local_official", "professional", "verifier", "marketer", "management"]), name="role_code_valid")),
        migrations.CreateModel(
            name="Permission",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=100, unique=True)),
                ("name", models.CharField(max_length=150)),
                ("description", models.TextField(blank=True)),
            ],
            options={"ordering": ["code"]},
        ),
        migrations.CreateModel(
            name="RolePermission",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("permission", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="role_permissions", to="authorization.permission")),
                ("role", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="role_permissions", to="authorization.role")),
            ],
        ),
        migrations.CreateModel(
            name="UserRole",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(default=True)),
                ("assigned_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="role_assignments_made", to=settings.AUTH_USER_MODEL)),
                ("role", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="user_roles", to="authorization.role")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="user_roles", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(model_name="rolepermission", constraint=models.UniqueConstraint(fields=("role", "permission"), name="uniq_role_permission")),
        migrations.AddConstraint(model_name="userrole", constraint=models.UniqueConstraint(fields=("user", "role"), name="uniq_user_role")),
        migrations.AddIndex(model_name="userrole", index=models.Index(fields=["user", "is_active"], name="userrole_active_idx")),
        migrations.RunPython(seed_roles, migrations.RunPython.noop),
]
