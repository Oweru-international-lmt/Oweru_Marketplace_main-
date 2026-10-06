import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("payments", "0002_financial_guards"), ("deals", "0004_deal_cancelled_state"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(
        name="FinancialNotice",
        fields=[
            ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("purpose", models.CharField(max_length=32)),
            ("sent_at", models.DateTimeField(null=True, blank=True)),
            ("recipient", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT)),
            ("sent_by", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT, null=True, blank=True, related_name="sent_financial_notices")),
            ("lead", models.ForeignKey(to="leads.lead", on_delete=django.db.models.deletion.PROTECT, null=True, blank=True)),
            ("deal", models.ForeignKey(to="deals.deal", on_delete=django.db.models.deletion.PROTECT, null=True, blank=True)),
        ],
        options={"constraints": [
            models.UniqueConstraint(fields=["recipient", "purpose", "lead"], condition=models.Q(lead__isnull=False), name="notice_lead_unique"),
            models.UniqueConstraint(fields=["recipient", "purpose", "deal"], condition=models.Q(deal__isnull=False), name="notice_deal_unique"),
        ]},
    )]
