from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("analysis", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="analysisjob",
            name="idempotency_key",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="SHA-256 fingerprint of (question, sorted document_ids, workflow_type). "
                "Prevents duplicate jobs on client retries.",
                max_length=64,
                null=True,
                unique=True,
            ),
        ),
    ]
