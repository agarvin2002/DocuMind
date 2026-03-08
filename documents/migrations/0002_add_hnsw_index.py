"""
Add HNSW approximate nearest-neighbour index on DocumentChunk.embedding.

Without this index, every vector search scans every row in the chunks table
(O(n)). HNSW reduces search to O(log n), which is required for any meaningful
document collection.

atomic=False is required because CREATE INDEX CONCURRENTLY cannot run inside
a transaction. CONCURRENTLY means existing reads/writes are not blocked while
the index builds — important in production where the table may already have data.
"""

from django.db import migrations


class Migration(migrations.Migration):
    atomic = False  # required for CONCURRENTLY

    dependencies = [
        ("documents", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS documents_chunk_embedding_hnsw_idx
                ON documents_documentchunk
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64);
            """,
            reverse_sql="""
                DROP INDEX IF EXISTS documents_chunk_embedding_hnsw_idx;
            """,
        )
    ]
