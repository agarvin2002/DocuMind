"""
retrieval/vector_store.py — Adapter that wraps the vector search function with logging.

The actual database query lives in documents/selectors.py (vector_search_chunks).
VectorStore wraps it so the pipeline has a clean, observable interface.

Usage:
    from retrieval.vector_store import VectorStore
    from documents.selectors import vector_search_chunks

    store = VectorStore(search_fn=vector_search_chunks)
    results = store.search(embedding, document_id, k=10)
"""

import logging
import uuid

from retrieval.protocols import VectorSearchPort
from retrieval.schemas import ChunkSearchResult

logger = logging.getLogger(__name__)


class VectorStore:
    """
    Adapter that adds logging around the injected vector search function.

    Accepts any callable that satisfies VectorSearchPort — in production this
    is vector_search_chunks from documents/selectors.py; in tests it can be
    any fake that matches the same signature.
    """

    def __init__(self, search_fn: VectorSearchPort) -> None:
        self._search_fn = search_fn

    def search(
        self,
        embedding: list[float],
        document_id: uuid.UUID,
        k: int,
    ) -> list[ChunkSearchResult]:
        """Run vector similarity search and return the top-k results."""
        logger.debug(
            "Vector store search starting",
            extra={"document_id": str(document_id), "k": k},
        )
        results = self._search_fn(embedding, document_id, k)
        logger.debug(
            "Vector store search complete",
            extra={"document_id": str(document_id), "result_count": len(results)},
        )
        return results
