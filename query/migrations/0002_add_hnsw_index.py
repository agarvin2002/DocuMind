"""
Add HNSW approximate nearest-neighbour index on SemanticCacheEntry.embedding.

Without this index every cache lookup scans the entire table (O(n)).
HNSW reduces search to O(log n), which is required for a useful cache.

atomic=False is required because CREATE INDEX CONCURRENTLY cannot run inside
a transaction. CONCURRENTLY means reads and writes are not blocked while the
index builds — important if the cache table already has rows.
"""

from django.db import migrations


class Migration(migrations.Migration):
    atomic = False  # required for CONCURRENTLY

    dependencies = [
        ("query", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS query_cache_embedding_hnsw_idx
                ON query_semanticcacheentry
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64);
            """,
            reverse_sql="""
                DROP INDEX IF EXISTS query_cache_embedding_hnsw_idx;
            """,
        )
    ]
