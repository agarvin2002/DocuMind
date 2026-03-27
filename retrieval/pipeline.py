"""
retrieval/pipeline.py — Orchestrates the full hybrid retrieval sequence.

Search sequence:
    1. Embed query          → 384-dim vector
    2. Vector search        → top (k * candidate_multiplier) semantic candidates
    3. Keyword search       → top (k * candidate_multiplier) BM25 candidates
    4. RRF fusion           → merged and de-duplicated candidate list
    5. Cross-encoder rerank → re-score fused candidates by reading query + chunk together
    6. Return top k

candidate_multiplier=3 ensures the reranker has a wide enough pool to surface
the best k results, compensating for blind spots in each individual search method.

Usage:
    from retrieval.pipeline import RetrievalPipeline

    pipeline = RetrievalPipeline(
        embedder=embedder,
        vector_search_fn=vector_search_chunks,
        keyword_search_fn=keyword_search_chunks,
        reranker=reranker,
    )
    results = pipeline.run(query="what are the risks?", document_id=doc_id, k=10)
"""

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError

from retrieval.hybrid import HybridFusion
from retrieval.protocols import (
    KeywordSearchPort,
    QueryEmbedderPort,
    RerankerPort,
    VectorSearchPort,
)
from retrieval.schemas import ChunkSearchResult
from retrieval.vector_store import VectorStore

logger = logging.getLogger(__name__)


class RetrievalPipeline:
    """
    Combines vector search, BM25 keyword search, RRF fusion, and cross-encoder
    reranking into a single retrieval call.

    All dependencies are injected at construction time so the pipeline contains
    no Django imports and can be tested with lightweight in-memory fakes.
    """

    def __init__(
        self,
        embedder: QueryEmbedderPort,
        vector_search_fn: VectorSearchPort,
        keyword_search_fn: KeywordSearchPort,
        reranker: RerankerPort,
        candidate_multiplier: int = 3,
        search_timeout_seconds: float = 5.0,
    ) -> None:
        self._embedder = embedder
        self._vector_store = VectorStore(search_fn=vector_search_fn)
        self._keyword_search_fn = keyword_search_fn
        self._reranker = reranker
        self._fusion = HybridFusion()
        self._candidate_multiplier = candidate_multiplier
        self._search_timeout_seconds = search_timeout_seconds

    def run(
        self,
        query: str,
        document_id: uuid.UUID,
        k: int,
    ) -> list[ChunkSearchResult]:
        """
        Execute the full retrieval pipeline and return the top-k results.

        Args:
            query: The user's search query string.
            document_id: UUID of the document to search within.
            k: Number of final results to return.

        Returns:
            List of ChunkSearchResult ordered by cross-encoder score descending.
            May be shorter than k if the document has fewer matching chunks.
        """
        candidates_k = k * self._candidate_multiplier

        logger.info(
            "Retrieval pipeline starting",
            extra={
                "document_id": str(document_id),
                "k": k,
                "candidates_k": candidates_k,
            },
        )

        embedding = self._embedder.embed_single(query)

        # Vector search (pgvector DB round-trip) and keyword search (Redis + BM25) are
        # independent — run them concurrently to cut wall-clock latency by ~50–150ms.
        # The timeout prevents a hung pgvector query or Redis call from blocking a
        # gunicorn worker indefinitely (search_timeout_seconds from settings).
        with ThreadPoolExecutor(max_workers=2) as executor:
            vector_future = executor.submit(
                self._vector_store.search, embedding, document_id, candidates_k
            )
            keyword_future = executor.submit(
                self._keyword_search_fn, query, document_id, candidates_k
            )
            try:
                vector_results = vector_future.result(
                    timeout=self._search_timeout_seconds
                )
                keyword_results = keyword_future.result(
                    timeout=self._search_timeout_seconds
                )
            except FutureTimeoutError:
                logger.error(
                    "Retrieval search timed out",
                    extra={
                        "document_id": str(document_id),
                        "timeout_seconds": self._search_timeout_seconds,
                    },
                )
                raise

        fused_results = self._fusion.fuse(vector_results, keyword_results)
        reranked_results = self._reranker.rerank(query, fused_results)
        final_results = reranked_results[:k]

        logger.info(
            "Retrieval pipeline complete",
            extra={
                "document_id": str(document_id),
                "vector_count": len(vector_results),
                "keyword_count": len(keyword_results),
                "fused_count": len(fused_results),
                "final_count": len(final_results),
            },
        )
        return final_results
