"""
ingestion/embedders.py — Convert text chunks into embedding vectors.

Usage:
    from ingestion.embedders import SentenceTransformerEmbedder, get_embedder

    # Preferred: shared process-level singleton (avoids reloading ~90MB model per task)
    embedder = get_embedder()
    embeddings = embedder.embed_batch(["first chunk text", "second chunk text"])
    # [[0.12, 0.87, ...], [0.34, 0.56, ...]]  — one list of 384 floats per input

Note:
    The first call downloads the model (~90MB) from HuggingFace to ~/.cache/huggingface/.
    Subsequent calls use the cached model. Set the EMBEDDING_MODEL_NAME environment
    variable to override the default model. Set EMBEDDING_BATCH_SIZE to control
    how many chunks are encoded per forward pass (default 32, configurable via settings).
"""

import logging
import os
import threading

from core.exceptions import EmbeddingError

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "all-MiniLM-L6-v2"

# ---------------------------------------------------------------------------
# Process-level singleton — the SentenceTransformer model (~90MB) is loaded
# once per Celery worker process, not once per task. Without this, every
# ingest_document task constructs a new IngestionPipeline which creates a new
# SentenceTransformerEmbedder, causing a 2-3s model reload for every document.
# ---------------------------------------------------------------------------
_embedder_instance: "SentenceTransformerEmbedder | None" = None
_embedder_lock = threading.Lock()


def get_embedder() -> "SentenceTransformerEmbedder":
    """
    Return the shared process-level SentenceTransformerEmbedder singleton.

    Thread-safe: uses double-checked locking so the model is loaded only once
    even if two Celery tasks start simultaneously in the same worker process.
    """
    global _embedder_instance
    if _embedder_instance is None:
        with _embedder_lock:
            if _embedder_instance is None:
                _embedder_instance = SentenceTransformerEmbedder()
    return _embedder_instance


class EmbeddingGenerationError(EmbeddingError):
    """Raised when the embedding model fails to load or encode a batch of texts."""


class SentenceTransformerEmbedder:
    """
    Generates 384-dimensional embeddings using sentence-transformers.

    The model is loaded lazily on the first embed_batch() call to avoid
    slowing down application startup when this module is imported.
    """

    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = (
            model_name or os.environ.get("EMBEDDING_MODEL_NAME") or _DEFAULT_MODEL
        )
        # Deferred to first embed_batch() call — not loaded at construction time.
        self._model = None

    def _load_model(self) -> None:
        """Load the sentence-transformer model on first use."""
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer

            logger.info(
                "Loading embedding model",
                extra={"model_name": self._model_name},
            )
            # Force CPU to avoid MPS crashes in forked Celery worker processes.
            # macOS MPS context is not fork-safe; CPU is portable and sufficient
            # for development and CI. Override with EMBEDDING_DEVICE in production
            # if running on a dedicated GPU host (non-forked concurrency).
            device = os.environ.get("EMBEDDING_DEVICE", "cpu")
            self._model = SentenceTransformer(self._model_name, device=device)
        except Exception as e:  # noqa: BLE001
            raise EmbeddingGenerationError(
                f"Failed to load embedding model {self._model_name!r}: {e}"
            ) from e

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Embed a list of texts, internally chunked into fixed-size mini-batches.

        Sending all texts to SentenceTransformer.encode() at once risks OOM on
        large documents (200-page PDF → 600+ chunks × ~4KB each). Mini-batching
        caps peak RAM usage while preserving throughput on CPU workers.

        Batch size is read from EMBEDDING_BATCH_SIZE in settings (default 32).
        Falls back to 32 when Django settings are not yet configured (tests, CLI).

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors, one per input text.
            Each vector is a list of 384 floats.

        Raises:
            EmbeddingGenerationError: if the model fails to load or encode.
        """
        if not texts:
            return []

        self._load_model()

        batch_size = self._get_batch_size()
        result: list[list[float]] = []

        try:
            for start in range(0, len(texts), batch_size):
                mini_batch = texts[start : start + batch_size]
                # convert_to_numpy=True returns numpy arrays; .tolist() converts
                # them to plain Python lists so no numpy dependency leaks to callers.
                batch_embeddings = self._model.encode(mini_batch, convert_to_numpy=True)
                result.extend(vec.tolist() for vec in batch_embeddings)
        except Exception as e:  # noqa: BLE001
            raise EmbeddingGenerationError(f"Embedding generation failed: {e}") from e

        logger.debug(
            "Batch embedding complete",
            extra={
                "text_count": len(texts),
                "batch_size": batch_size,
                "dimensions": len(result[0]) if result else 0,
                "model": self._model_name,
            },
        )
        return result

    @staticmethod
    def _get_batch_size() -> int:
        """Read EMBEDDING_BATCH_SIZE from settings, falling back to 32."""
        try:
            from django.conf import settings

            return int(getattr(settings, "EMBEDDING_BATCH_SIZE", 32))
        except Exception:  # noqa: BLE001
            return 32

    def embed_single(self, text: str) -> list[float]:
        """Embed one text string and return its vector."""
        return self.embed_batch([text])[0]
