from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0002_add_hnsw_index"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="documentchunk",
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name="documentchunk",
            constraint=models.UniqueConstraint(
                fields=["document", "chunk_index"],
                name="documents_documentchunk_document_chunk_index_uniq",
            ),
        ),
    ]
