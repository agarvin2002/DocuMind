"""
query/models.py — database models for the query layer.

SemanticCacheEntry stores question–answer pairs with their query embeddings
so semantically equivalent future questions can be answered without calling
the LLM. The HNSW index (added in 0002_add_hnsw_index.py) makes the pgvector
cosine similarity lookup fast.
"""

import uuid

from django.db import models
from pgvector.django import VectorField


class SemanticCacheEntry(models.Model):
    """
    One cached question–answer pair for a specific document.

    Lifecycle:
      - Written after every successful LLM answer.
      - Read before calling the LLM — similar queries return this instead.
      - Deleted automatically when the parent Document is deleted (CASCADE).
      - Filtered by created_at on lookup — entries older than TTL are ignored.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # CASCADE: deleting a document purges all its cache entries automatically.
    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.CASCADE,
        related_name="cache_entries",
    )
    query_text = models.TextField()
    # 384 dimensions matches all-MiniLM-L6-v2 (the embedder used throughout).
    embedding = VectorField(dimensions=384)
    # Stores {"answer": "...", "citations": [...]} — serializable to SSE events.
    answer_json = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Index added separately in 0002_add_hnsw_index.py (requires atomic=False).
        pass

    def __str__(self) -> str:
        return f"CacheEntry({self.document_id}, {self.query_text[:40]!r})"
