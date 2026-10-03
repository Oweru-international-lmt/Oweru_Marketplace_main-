import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="Role",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=50, unique=True)),
                ("name", models.CharField(max_length=100)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["code"]},
        ),
        migrations.CreateModel(
            name="UserRole",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("assigned_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("is_active", models.BooleanField(default=True)),
                ("assigned_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="m01_role_assignments_made", to=settings.AUTH_USER_MODEL)),
                ("role", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="user_assignments", to="roles.role")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="m01_roles", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-assigned_at"]},
        ),
        migrations.AddConstraint(
            model_name="userrole",
            constraint=models.UniqueConstraint(
                condition=Q(is_active=True),
                fields=("user", "role"),
                name="uniq_active_m01_user_role",
            ),
        ),
        migrations.AddIndex(
            model_name="userrole",
            index=models.Index(fields=["user", "is_active"], name="m01_userrole_active_idx"),
        ),
        migrations.AddIndex(
            model_name="userrole",
            index=models.Index(fields=["role", "is_active"], name="m01_role_active_idx"),
        ),
    ]
