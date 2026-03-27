"""
documents/selectors.py — Read-only database queries for the documents app.

Usage:
    from documents.selectors import get_document_by_id, list_documents
"""

import logging
import uuid

import redis as redis_lib
from pgvector.django import CosineDistance

from core.redis import get_redis_client
from documents.constants import BM25_CACHE_KEY_PREFIX, BM25_INDEX_TTL_SECONDS
from documents.exceptions import DocumentNotFoundError
from documents.models import Document, DocumentChunk
from retrieval.bm25 import BM25Index
from retrieval.schemas import ChunkSearchResult

logger = logging.getLogger(__name__)


def get_document_by_id(document_id: uuid.UUID, *, api_key=None) -> Document:
    """
    Fetch a single Document by primary key.

    When api_key is provided the query is scoped to that key's documents,
    preventing cross-key information disclosure (C-1 authorization fix).

    Args:
        document_id: UUID of the document to fetch.
        api_key: Optional APIKey instance. When set, only returns the document
                 if it belongs to this key.

    Raises:
        DocumentNotFoundError: if no Document with that ID exists, or if it
                               exists but belongs to a different API key.
    """
    try:
        qs = Document.objects.filter(pk=document_id)
        if api_key is not None:
            qs = qs.filter(api_key=api_key)
        return qs.get()
    except Document.DoesNotExist:
        raise DocumentNotFoundError(f"Document {document_id} not found")


def list_documents(status: str | None = None, *, api_key=None):
    """
    Return Documents, optionally filtered by status and/or owning API key.

    When api_key is provided only that key's documents are returned.
    Returns a lazy QuerySet so callers can chain further filters if needed.

    Args:
        status: Optional Document.Status value to filter by.
        api_key: Optional APIKey instance for per-key isolation.
    """
    qs = Document.objects.all().order_by("-created_at")
    if api_key is not None:
        qs = qs.filter(api_key=api_key)
    if status is not None:
        qs = qs.filter(status=status)
    return qs


def get_chunks_for_document(document_id: uuid.UUID):
    """
    Return all DocumentChunk rows for a document, ordered by chunk_index.
    """
    return DocumentChunk.objects.filter(document_id=document_id).order_by("chunk_index")


def vector_search_chunks(
    embedding: list[float],
    document_id: uuid.UUID,
    k: int,
) -> list[ChunkSearchResult]:
    """
    Return the top-k chunks whose embeddings are closest to the query embedding.

    Uses pgvector cosine distance. Distance is converted to similarity score
    (1 - distance) so higher scores mean more relevant, consistent with BM25
    and cross-encoder conventions.
    """
    rows = (
        DocumentChunk.objects.filter(document_id=document_id)
        .exclude(embedding=None)
        .annotate(distance=CosineDistance("embedding", embedding))
        .order_by("distance")
        .select_related("document")[:k]
    )

    results = []
    for row in rows:
        results.append(
            ChunkSearchResult(
                chunk_id=str(row.id),
                document_id=str(row.document_id),
                document_title=row.document.title,
                chunk_index=row.chunk_index,
                child_text=row.child_text,
                parent_text=row.parent_text,
                page_number=row.page_number,
                score=max(0.0, 1.0 - float(row.distance)),
            )
        )

    logger.debug(
        "Vector search complete",
        extra={"document_id": str(document_id), "k": k, "results": len(results)},
    )
    return results


def keyword_search_chunks(
    query: str,
    document_id: uuid.UUID,
    k: int,
) -> list[ChunkSearchResult]:
    """
    Return the top-k chunks that best match the query using BM25 keyword scoring.

    Loads the BM25 index from Redis (rebuilds from DB if not cached), searches
    for matching chunk positions, then fetches the full rows from the database.
    """
    bm25_index = _get_bm25_index_or_rebuild(document_id)
    position_scores = bm25_index.search(query, k)

    if not position_scores:
        return []

    # Map BM25 corpus positions back to chunk_index values.
    # The index was built from chunks ordered by chunk_index, so position == chunk_index.
    chunk_indices = [pos for pos, _ in position_scores]

    rows = DocumentChunk.objects.filter(
        document_id=document_id,
        chunk_index__in=chunk_indices,
    ).select_related("document")

    row_by_index = {row.chunk_index: row for row in rows}

    results = []
    for pos, score in position_scores:
        row = row_by_index.get(pos)
        if row is None:
            continue
        results.append(
            ChunkSearchResult(
                chunk_id=str(row.id),
                document_id=str(row.document_id),
                document_title=row.document.title,
                chunk_index=row.chunk_index,
                child_text=row.child_text,
                parent_text=row.parent_text,
                page_number=row.page_number,
                score=score,
            )
        )

    logger.debug(
        "Keyword search complete",
        extra={"document_id": str(document_id), "k": k, "results": len(results)},
    )
    return results


def _get_bm25_index_or_rebuild(document_id: uuid.UUID) -> BM25Index:
    """
    Load the BM25 index for a document from Redis, rebuilding from DB if missing.

    Redis key: BM25_CACHE_KEY_PREFIX:{document_id}
    TTL: BM25_INDEX_TTL_SECONDS (7 days)

    Redis failures are non-fatal — the index is rebuilt from the database and
    the search continues. A warning is logged so the gap is visible in monitoring.
    """
    redis_key = f"{BM25_CACHE_KEY_PREFIX}:{document_id}"
    cached = None

    try:
        r = get_redis_client()
        cached = r.get(redis_key)
        if cached is not None:
            logger.debug(
                "BM25 index loaded from Redis", extra={"document_id": str(document_id)}
            )
    except redis_lib.RedisError as e:
        logger.warning(
            "Redis unavailable when loading BM25 index — rebuilding from DB",
            extra={"document_id": str(document_id), "error_type": type(e).__name__},
        )

    if cached is not None:
        return BM25Index.from_bytes(cached)

    # Cache miss or Redis down — rebuild from database.
    logger.info(
        "Rebuilding BM25 index from DB", extra={"document_id": str(document_id)}
    )
    chunks = (
        DocumentChunk.objects.filter(document_id=document_id)
        .order_by("chunk_index")
        .values_list("child_text", flat=True)
    )
    bm25_index = BM25Index.build(list(chunks))

    try:
        r = get_redis_client()
        r.setex(redis_key, BM25_INDEX_TTL_SECONDS, bm25_index.serialize())
    except redis_lib.RedisError as e:
        logger.warning(
            "Failed to cache rebuilt BM25 index in Redis",
            extra={"document_id": str(document_id), "error_type": type(e).__name__},
        )

    return bm25_index
