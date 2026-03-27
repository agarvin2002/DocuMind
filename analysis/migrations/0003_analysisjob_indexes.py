from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("analysis", "0002_analysisjob_idempotency_key"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="analysisjob",
            index=models.Index(
                fields=["created_at"], name="analysisjob_created_at_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="analysisjob",
            index=models.Index(
                fields=["status", "created_at"],
                name="analysisjob_status_created_idx",
            ),
        ),
    ]
