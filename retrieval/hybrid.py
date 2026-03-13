"""
retrieval/hybrid.py — Reciprocal Rank Fusion for combining vector and keyword results.

RRF merges two ranked lists by scoring each result as the sum of 1/(k + rank)
across all lists where it appears. Results present in both lists score ~2x higher
than results present in only one, making cross-list agreement the signal for relevance.

Reference: Cormack, Clarke, Buettcher (2009) — "Reciprocal Rank Fusion outperforms
Condorcet and individual rank learning methods."

Usage:
    fusion = HybridFusion(k=60)
    results = fusion.fuse(vector_results, keyword_results)
"""

import logging
from dataclasses import replace

from retrieval.schemas import ChunkSearchResult

logger = logging.getLogger(__name__)

_RRF_K = 60  # Standard constant from the 2009 RRF paper.


class HybridFusion:
    """
    Merges vector search results and BM25 keyword results using Reciprocal Rank Fusion.

    Chunks appearing in both lists score roughly 2x higher than single-list chunks.
    Handles empty input lists gracefully — returns the non-empty list with RRF scores.
    """

    def __init__(self, k: int = _RRF_K) -> None:
        self._k = k

    def fuse(
        self,
        vector_results: list[ChunkSearchResult],
        keyword_results: list[ChunkSearchResult],
    ) -> list[ChunkSearchResult]:
        """
        Combine two ranked lists into one using RRF scoring.

        Args:
            vector_results: Results from semantic vector search, ordered best-first.
            keyword_results: Results from BM25 keyword search, ordered best-first.

        Returns:
            Deduplicated list sorted by RRF score descending.
            Metadata (text, title, page) is taken from vector_results when a chunk
            appears in both lists, as vector search fetches it via select_related.
        """
        if not vector_results and not keyword_results:
            return []

        # Accumulate RRF scores: score += 1 / (k + rank) for each list.
        # rank is 1-based (rank 1 = best result).
        rrf_scores: dict[str, float] = {}
        metadata: dict[str, ChunkSearchResult] = {}

        for rank, result in enumerate(vector_results, start=1):
            rrf_scores[result.chunk_id] = rrf_scores.get(result.chunk_id, 0.0) + 1.0 / (self._k + rank)
            metadata[result.chunk_id] = result

        for rank, result in enumerate(keyword_results, start=1):
            rrf_scores[result.chunk_id] = rrf_scores.get(result.chunk_id, 0.0) + 1.0 / (self._k + rank)
            # Only store metadata from keyword results if not already stored from vector results.
            if result.chunk_id not in metadata:
                metadata[result.chunk_id] = result

        # Build final results with updated RRF scores, sorted highest first.
        fused = [
            replace(metadata[chunk_id], score=score)
            for chunk_id, score in sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        ]

        logger.debug(
            "Hybrid fusion complete",
            extra={
                "vector_count": len(vector_results),
                "keyword_count": len(keyword_results),
                "fused_count": len(fused),
            },
        )
        return fused
