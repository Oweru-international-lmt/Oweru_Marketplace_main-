from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("deals", "0002_initial")]
    operations = [
        migrations.AddField(model_name="deal", name="owner_bank_snapshot", field=models.JSONField(default=dict, editable=False)),
        migrations.AddField(model_name="deal", name="oweru_bank_snapshot", field=models.JSONField(default=dict, editable=False)),
    ]
