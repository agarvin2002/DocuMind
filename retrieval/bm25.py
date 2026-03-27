"""
retrieval/bm25.py — BM25 keyword search index for exact-match retrieval.

Phase 2 builds the index during ingestion.
Phase 3 adds search queries and Redis persistence.

Usage:
    from retrieval.bm25 import BM25Index

    index = BM25Index.build(["first chunk text", "second chunk text"])
    data = index.serialize()           # bytes — store in Redis or file
    index2 = BM25Index.from_bytes(data)  # reconstruct from bytes
"""

import logging
import pickle

from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stemming (optional — enabled via BM25_USE_STEMMING env var)
# ---------------------------------------------------------------------------
# Module-level cache so the stemmer and stopword set are loaded once per process.
_stemmer = None
_stopwords: set[str] | None = None


def _get_stemmer_and_stopwords():
    global _stemmer, _stopwords
    if _stemmer is None:
        import nltk
        from nltk.corpus import stopwords as sw
        from nltk.stem import PorterStemmer

        for resource in ("corpora/stopwords", "tokenizers/punkt"):
            try:
                nltk.data.find(resource)
            except LookupError:
                nltk.download(resource.split("/")[1], quiet=True)

        _stemmer = PorterStemmer()
        _stopwords = set(sw.words("english"))
    return _stemmer, _stopwords


def _use_stemming() -> bool:
    try:
        from django.conf import settings

        return bool(getattr(settings, "BM25_USE_STEMMING", False))
    except Exception:  # noqa: BLE001
        return False


def _tokenize(text: str) -> list[str]:
    tokens = text.lower().split()
    if not _use_stemming():
        return tokens
    stemmer, stopwords = _get_stemmer_and_stopwords()
    return [stemmer.stem(t) for t in tokens if t not in stopwords]


class BM25Index:
    """
    Thin wrapper around BM25Okapi with build and serialisation support.

    Keeps the rank-bm25 implementation detail hidden behind a stable interface
    so callers (pipeline, retrieval) are not coupled to the underlying library.
    """

    def __init__(self, index: BM25Okapi, corpus: list[list[str]]) -> None:
        self._index = index
        self._corpus = corpus

    @classmethod
    def build(cls, texts: list[str]) -> "BM25Index":
        """
        Build a BM25 index from a list of text strings.

        Args:
            texts: One string per document chunk.

        Returns:
            A BM25Index ready for serialisation or search.

        Raises:
            ValueError: if texts is empty — BM25Okapi raises on empty corpus.
        """
        if not texts:
            raise ValueError("Cannot build BM25 index from an empty text list")

        tokenized = [_tokenize(t) for t in texts]
        logger.debug("Building BM25 index", extra={"corpus_size": len(tokenized)})
        index = BM25Okapi(tokenized)
        return cls(index, tokenized)

    def serialize(self) -> bytes:
        """Convert the index to bytes for caching in Redis or on disk."""
        return pickle.dumps({"index": self._index, "corpus": self._corpus})

    @classmethod
    def from_bytes(cls, data: bytes) -> "BM25Index":
        """Reconstruct a BM25Index from serialised bytes."""
        payload = pickle.loads(data)  # noqa: S301 — only called with trusted internal bytes
        return cls(payload["index"], payload["corpus"])

    def search(self, query_text: str, k: int) -> list[tuple[int, float]]:
        """
        Return the top-k matching corpus positions and their BM25 scores.

        Args:
            query_text: The search query string.
            k: Maximum number of results to return.

        Returns:
            List of (corpus_position, score) pairs sorted by score descending.
            corpus_position == chunk_index of the matching DocumentChunk.
            Chunks with a score of exactly 0.0 (no query term present) are excluded.
            Negative scores (high-frequency term epsilon floor) are kept.
        """
        if not query_text.strip():
            return []

        tokens = _tokenize(query_text)
        raw_scores: list[float] = self._index.get_scores(tokens).tolist()

        # Drop exactly-zero scores — no query term appeared in those chunks.
        # Keep negative scores — BM25Okapi floors high-frequency term IDF to
        # epsilon * average_idf, which can be negative. Those chunks still matched.
        scored = [(pos, score) for pos, score in enumerate(raw_scores) if score != 0.0]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]

    @property
    def corpus_size(self) -> int:
        """Number of documents (chunks) in the index."""
        return len(self._corpus)
