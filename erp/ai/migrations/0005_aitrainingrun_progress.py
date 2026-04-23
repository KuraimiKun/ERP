from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("erp_ai", "0004_aitrainingrun"),
    ]

    operations = [
        migrations.AddField(
            model_name="aitrainingrun",
            name="progress_step",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="aitrainingrun",
            name="progress_total",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="aitrainingrun",
            name="progress_label",
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
