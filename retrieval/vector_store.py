"""
retrieval/vector_store.py — Persist and query document chunks in pgvector.

Phase 2 implements the write side (save_chunks).
Phase 3 will add the read side (semantic search queries).

Usage:
    from retrieval.vector_store import save_chunks
    save_chunks(document_id, chunks, embeddings)
"""

import logging
import uuid

from ingestion.chunkers import ChunkData

logger = logging.getLogger(__name__)


def save_chunks(
    document_id: uuid.UUID,
    chunks: list[ChunkData],
    embeddings: list[list[float]],
) -> None:
    """
    Persist a document's chunks and their embeddings to PostgreSQL/pgvector.

    DocumentChunk is imported inside this function — not at module level — so
    this module can be imported without Django being configured, which keeps
    unit tests fast and decoupled from the database.

    Args:
        document_id: UUID of the parent Document row.
        chunks: ChunkData objects produced by the chunker.
        embeddings: Embedding vectors, one per chunk (same order as chunks).

    Raises:
        ValueError: if len(chunks) != len(embeddings).
        Any Django ORM exception propagates to the caller (tasks.py handles it).
    """
    if len(chunks) != len(embeddings):
        raise ValueError(
            f"chunks ({len(chunks)}) and embeddings ({len(embeddings)}) must have "
            "the same length"
        )

    if not chunks:
        logger.debug(
            "save_chunks called with empty list — nothing to persist",
            extra={"document_id": str(document_id)},
        )
        return

    # Local import keeps this module importable without a running Django instance.
    from documents.models import DocumentChunk

    chunk_objects = [
        DocumentChunk(
            document_id=document_id,
            chunk_index=chunk.chunk_index,
            child_text=chunk.child_text,
            parent_text=chunk.parent_text,
            page_number=chunk.page_number,
            embedding=embedding,
        )
        for chunk, embedding in zip(chunks, embeddings)
    ]

    # bulk_create writes all rows in batches — far fewer SQL round-trips than
    # calling .save() once per chunk, which matters at scale.
    DocumentChunk.objects.bulk_create(chunk_objects, batch_size=500)

    logger.info(
        "Chunks saved to vector store",
        extra={"document_id": str(document_id), "chunk_count": len(chunk_objects)},
    )
