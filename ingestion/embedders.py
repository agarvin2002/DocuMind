"""
ingestion/embedders.py — Convert text chunks into embedding vectors.

Usage:
    from ingestion.embedders import SentenceTransformerEmbedder

    embedder = SentenceTransformerEmbedder()
    embeddings = embedder.embed_batch(["first chunk text", "second chunk text"])
    # [[0.12, 0.87, ...], [0.34, 0.56, ...]]  — one list of 384 floats per input

Note:
    The first call downloads the model (~90MB) from HuggingFace to ~/.cache/huggingface/.
    Subsequent calls use the cached model. Set the EMBEDDING_MODEL_NAME environment
    variable to override the default model.
"""

import logging
import os

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "all-MiniLM-L6-v2"


class EmbeddingGenerationError(Exception):
    """
    Raised when embedding generation fails.

    Kept as a plain Python exception so this module can be imported and tested
    without Django being configured. The task layer translates this to
    the appropriate Django exception if needed.
    """


class SentenceTransformerEmbedder:
    """
    Generates 384-dimensional embeddings using sentence-transformers.

    The model is loaded lazily on the first embed_batch() call to avoid
    slowing down application startup when this module is imported.
    """

    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = (
            model_name
            or os.environ.get("EMBEDDING_MODEL_NAME")
            or _DEFAULT_MODEL
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
        Embed a list of texts in a single batched forward pass.

        Batching all texts together is significantly faster than embedding
        one text at a time, as the model can parallelise the computation.

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

        try:
            # convert_to_numpy=False returns pytorch tensors; .tolist() converts
            # them to plain Python lists so no numpy dependency leaks to callers.
            embeddings = self._model.encode(texts, convert_to_numpy=True)
            result: list[list[float]] = [vec.tolist() for vec in embeddings]
        except Exception as e:  # noqa: BLE001
            raise EmbeddingGenerationError(
                f"Embedding generation failed: {e}"
            ) from e

        logger.debug(
            "Batch embedding complete",
            extra={
                "text_count": len(texts),
                "dimensions": len(result[0]) if result else 0,
                "model": self._model_name,
            },
        )
        return result
