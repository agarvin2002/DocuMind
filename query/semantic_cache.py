"""
query/semantic_cache.py — SemanticCache implementation.

Uses pgvector cosine distance to find semantically equivalent cached queries.
Both lookup() and store() are wrapped in try/except — the cache is an
optimisation, not a dependency. Any failure falls through to the LLM pipeline.
"""

import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from pgvector.django import CosineDistance

logger = logging.getLogger(__name__)


class SemanticCache:
    """
    Implements SemanticCachePort using pgvector cosine similarity.

    Reuses the module-level embedder singleton from query/services.py
    (via lazy import) to avoid loading the sentence-transformer model twice.
    """

    def lookup(self, query: str, document_id: uuid.UUID) -> dict | None:
        """
        Returns cached answer_json if a semantically similar query exists
        for this document within the TTL. Returns None on miss or any error.

        The pgvector SQL this generates:
            SELECT id, answer_json, (embedding <=> %s) AS distance
            FROM query_semanticcacheentry
            WHERE document_id = %s
              AND created_at >= %s
              AND (embedding <=> %s) <= 0.08
            ORDER BY distance ASC
            LIMIT 1;
        """
        try:
            from query.models import SemanticCacheEntry
            from query.services import _get_embedder

            # Read at call-time so env-var overrides take effect without restart.
            # pgvector uses distance (0 = identical), so convert similarity → distance.
            distance_threshold = 1.0 - settings.SEMANTIC_CACHE_SIMILARITY_THRESHOLD
            ttl_days = settings.SEMANTIC_CACHE_TTL_DAYS

            query_embedding = _get_embedder().embed_single(query)
            cutoff = timezone.now() - timedelta(days=ttl_days)

            entry = (
                SemanticCacheEntry.objects.filter(
                    document_id=document_id,
                    created_at__gte=cutoff,
                )
                .annotate(distance=CosineDistance("embedding", query_embedding))
                .filter(distance__lte=distance_threshold)
                .order_by("distance")
                .first()
            )

            if entry is None:
                return None

            logger.debug(
                "Semantic cache hit",
                extra={
                    "document_id": str(document_id),
                    "similarity": round(1.0 - float(entry.distance), 4),
                },
            )
            return entry.answer_json

        except Exception as e:
            logger.warning(
                "Semantic cache lookup failed",
                extra={"error_type": type(e).__name__},
                exc_info=True,
            )
            return None  # treat as a miss — LLM pipeline handles it

    def store(
        self,
        query: str,
        document_id: uuid.UUID,
        answer_json: dict,
    ) -> None:
        """
        Embeds the query and persists a new cache entry.
        Failures are logged as warnings and silently swallowed —
        the user already received their answer.
        """
        try:
            from query.models import SemanticCacheEntry
            from query.services import _get_embedder

            embedding = _get_embedder().embed_single(query)
            SemanticCacheEntry.objects.create(
                document_id=document_id,
                query_text=query,
                embedding=embedding,
                answer_json=answer_json,
            )
            logger.info(
                "Semantic cache entry stored",
                extra={"document_id": str(document_id)},
            )
        except Exception as e:
            logger.warning(
                "Semantic cache store failed",
                extra={"error_type": type(e).__name__},
                exc_info=True,
            )
