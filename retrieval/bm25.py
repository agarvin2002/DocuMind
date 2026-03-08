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


def _tokenize(text: str) -> list[str]:
    # Simple whitespace tokenisation — lowercase + split.
    # More sophisticated tokenisation (stopwords, stemming) deferred to Phase 3
    # where it can be benchmarked against retrieval quality metrics.
    return text.lower().split()


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

    @property
    def corpus_size(self) -> int:
        """Number of documents (chunks) in the index."""
        return len(self._corpus)
