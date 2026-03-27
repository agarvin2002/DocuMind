"""
Add api_key foreign key to Document for per-key document isolation.

Without this field any authenticated API key can read any document UUID
(information disclosure). The FK enables the ownership filter in
documents/selectors.py so users can only access their own documents.

SET_NULL (not CASCADE) preserves documents when an API key is revoked —
the admin can still see them; they just become inaccessible via the API.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("authentication", "0001_initial"),
        ("documents", "0004_document_retry_count"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="api_key",
            field=models.ForeignKey(
                blank=True,
                db_index=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="documents",
                to="authentication.apikey",
            ),
        ),
    ]
