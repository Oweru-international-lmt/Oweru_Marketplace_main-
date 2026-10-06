from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("deals", "0003_deal_bank_snapshots")]
    operations = [
        migrations.RemoveConstraint(model_name="deal", name="deal_state_valid"),
        migrations.AddConstraint(model_name="deal", constraint=models.CheckConstraint(condition=models.Q(state__in=["OPEN", "COMPLETE", "CANCELLED"]), name="deal_state_valid")),
    ]
