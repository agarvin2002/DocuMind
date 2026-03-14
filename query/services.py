"""
query/services.py — Composition root for the retrieval pipeline.

This is the single place in the codebase that wires together:
    - retrieval/ (pure Python — no Django)
    - documents/ (Django ORM queries)
    - ingestion/ (embedder)

All imports are local to execute_search() to avoid circular import chains
at module load time (query → documents → models → apps → query).

Usage:
    from query.services import execute_search
    results = execute_search(query="what are the risks?", document_id=uuid, k=10)
"""

import logging
import threading
import uuid

from query.exceptions import NoRelevantChunksError
from retrieval.schemas import ChunkSearchResult

logger = logging.getLogger(__name__)

# Module-level lazy singletons — models are loaded once per process, not per request.
# Locks prevent two threads at startup from both seeing None and loading the model twice.
_embedder = None
_reranker = None
_pipeline = None
_embedder_lock = threading.Lock()
_reranker_lock = threading.Lock()
_pipeline_lock = threading.Lock()


def _get_embedder():
    global _embedder
    if _embedder is None:
        with _embedder_lock:
            if _embedder is None:
                from ingestion.embedders import SentenceTransformerEmbedder

                _embedder = SentenceTransformerEmbedder()
    return _embedder


def _get_reranker():
    global _reranker
    if _reranker is None:
        with _reranker_lock:
            if _reranker is None:
                from retrieval.reranker import CrossEncoderReranker

                _reranker = CrossEncoderReranker()
    return _reranker


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        with _pipeline_lock:
            if _pipeline is None:
                from documents.selectors import (
                    keyword_search_chunks,
                    vector_search_chunks,
                )
                from retrieval.pipeline import RetrievalPipeline

                _pipeline = RetrievalPipeline(
                    embedder=_get_embedder(),
                    vector_search_fn=vector_search_chunks,
                    keyword_search_fn=keyword_search_chunks,
                    reranker=_get_reranker(),
                )
    return _pipeline


def execute_search(
    query: str,
    document_id: uuid.UUID,
    k: int,
) -> list[ChunkSearchResult]:
    """
    Run the full retrieval pipeline for a single query against one document.

    Wires together the embedder, vector search, keyword search, RRF fusion,
    and cross-encoder reranking into a single call.

    Args:
        query: The user's search query string.
        document_id: UUID of the document to search within.
        k: Number of results to return.

    Returns:
        List of ChunkSearchResult ordered by relevance score descending.

    Raises:
        DocumentNotFoundError: if no document with document_id exists (404).
        NoRelevantChunksError: if the pipeline returns no results (404).
    """
    # Local import breaks the circular chain: query → documents → models → apps → query.
    from documents.selectors import get_document_by_id

    # Validate the document exists before running the expensive pipeline.
    get_document_by_id(document_id)  # raises DocumentNotFoundError if missing

    results = _get_pipeline().run(query=query, document_id=document_id, k=k)

    if not results:
        raise NoRelevantChunksError(
            f"No relevant chunks found for query in document {document_id}"
        )

    logger.info(
        "Search complete",
        extra={
            "document_id": str(document_id),
            "query_length": len(query),
            "result_count": len(results),
        },
    )
    return results
