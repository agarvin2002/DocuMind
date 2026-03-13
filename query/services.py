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
import uuid

from core.exceptions import DocuMindError
from retrieval.schemas import ChunkSearchResult

logger = logging.getLogger(__name__)


class NoRelevantChunksError(DocuMindError):
    """Raised when the retrieval pipeline returns no results for a query."""

    http_status_code = 404


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
    # Local imports break potential circular chains at module load time.
    from documents.selectors import (
        get_document_by_id,
        keyword_search_chunks,
        vector_search_chunks,
    )
    from ingestion.embedders import SentenceTransformerEmbedder
    from retrieval.pipeline import RetrievalPipeline
    from retrieval.reranker import CrossEncoderReranker

    # Validate the document exists before running the expensive pipeline.
    get_document_by_id(document_id)  # raises DocumentNotFoundError if missing

    pipeline = RetrievalPipeline(
        embedder=SentenceTransformerEmbedder(),
        vector_search_fn=vector_search_chunks,
        keyword_search_fn=keyword_search_chunks,
        reranker=CrossEncoderReranker(),
    )

    results = pipeline.run(query=query, document_id=document_id, k=k)

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
