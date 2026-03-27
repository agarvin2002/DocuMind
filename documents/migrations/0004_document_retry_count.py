from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0003_documentchunk_unique_constraint"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="retry_count",
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]
