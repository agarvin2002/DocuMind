"""
retrieval/reranker.py — Cross-encoder re-ranking for final relevance scoring.

The cross-encoder reads query + chunk together (unlike bi-encoders which score
each independently). This is slower but significantly more accurate, so it is
only run on the shortlist of candidates produced by hybrid fusion — not the
full corpus.

Model: cross-encoder/ms-marco-MiniLM-L-6-v2
    ~70MB, downloaded automatically from HuggingFace on first use.
    Trained on MS MARCO — Microsoft's large-scale question-answer dataset.

Usage:
    reranker = CrossEncoderReranker()
    reranked = reranker.rerank(query="what are the risks?", candidates=fused_results)
"""

import logging
import os
from dataclasses import replace

from core.exceptions import DocuMindError
from retrieval.constants import RERANKER_MAX_CANDIDATES
from retrieval.schemas import ChunkSearchResult

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class RerankerError(DocuMindError):
    """Raised when the cross-encoder model fails to load or score candidates."""


class CrossEncoderReranker:
    """
    Re-ranks a shortlist of candidates using a cross-encoder model.

    The model is loaded lazily on the first rerank() call to avoid slowing
    down Django startup when this module is imported.
    """

    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = model_name or _DEFAULT_MODEL
        self._model = None  # Deferred to first rerank() call.

    def _load_model(self) -> None:
        """Load the cross-encoder model on first use."""
        if self._model is not None:
            return
        try:
            from sentence_transformers import CrossEncoder

            logger.info(
                "Loading cross-encoder model",
                extra={"model_name": self._model_name},
            )
            device = os.environ.get("EMBEDDING_DEVICE", "cpu")
            self._model = CrossEncoder(self._model_name, device=device)
        except Exception as e:  # noqa: BLE001
            raise RerankerError(
                f"Failed to load cross-encoder model {self._model_name!r}: {e}"
            ) from e

    def rerank(
        self,
        query: str,
        candidates: list[ChunkSearchResult],
    ) -> list[ChunkSearchResult]:
        """
        Score each candidate by reading the query and chunk text together.

        Args:
            query: The original search query string.
            candidates: Shortlist of chunks to re-rank (typically k * candidate_multiplier).

        Returns:
            The same candidates re-ordered by cross-encoder score, highest first.

        Raises:
            RerankerError: if the model fails to load or score the candidates.
        """
        if not candidates:
            return []

        if len(candidates) > RERANKER_MAX_CANDIDATES:
            logger.warning(
                "Reranker candidate list truncated",
                extra={
                    "original_count": len(candidates),
                    "max": RERANKER_MAX_CANDIDATES,
                },
            )
            candidates = candidates[:RERANKER_MAX_CANDIDATES]

        self._load_model()

        pairs = [(query, result.child_text) for result in candidates]

        try:
            scores: list[float] = self._model.predict(pairs).tolist()
        except Exception as e:  # noqa: BLE001
            raise RerankerError(f"Cross-encoder scoring failed: {e}") from e

        if len(scores) != len(candidates):
            raise RerankerError(
                f"Cross-encoder returned {len(scores)} scores for {len(candidates)} candidates"
            )

        reranked = [
            replace(result, score=score) for result, score in zip(candidates, scores)
        ]
        reranked.sort(key=lambda r: r.score, reverse=True)

        logger.debug(
            "Cross-encoder reranking complete",
            extra={"candidate_count": len(candidates)},
        )
        return reranked
