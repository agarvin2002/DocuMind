"""
documents/services.py — Write operations for the documents app.

Usage:
    from documents.services import create_document, trigger_ingestion
"""

import logging
import uuid

import redis as redis_lib
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

from documents.exceptions import DocumentUploadError
from documents.models import Document, DocumentChunk
from ingestion.chunkers import ChunkData
from retrieval.bm25 import BM25Index

logger = logging.getLogger(__name__)

# Module-level pool — connections are reused across Celery tasks instead of torn down per call.
_redis_pool: redis_lib.ConnectionPool | None = None


def _get_redis_pool() -> redis_lib.ConnectionPool:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis_lib.ConnectionPool.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _redis_pool


def create_document(
    file: UploadedFile,
    title: str,
    original_filename: str,
    file_type: str,
) -> Document:
    """
    Persist a new Document record and upload the file to S3/MinIO.

    django-storages handles the file transfer to S3/MinIO automatically
    when doc.file.save() is called — we never call the S3 API directly.

    Raises:
        DocumentUploadError: if the file cannot be saved to storage.
    """
    try:
        doc = Document(
            title=title,
            original_filename=original_filename,
            file_type=file_type,
            file_size=file.size,
            status=Document.Status.PENDING,
        )
        doc.file.save(original_filename, file, save=True)
    except Exception as e:  # noqa: BLE001
        logger.error(
            "Failed to create document",
            extra={
                "original_filename": original_filename,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )
        raise DocumentUploadError(f"Could not save document to storage: {e}") from e

    logger.info(
        "Document created",
        extra={"document_id": str(doc.id), "title": title},
    )
    return doc


def trigger_ingestion(document_id: uuid.UUID) -> None:
    """
    Dispatch the Celery ingestion task for a document.

    The task import is local to this function to avoid a circular import:
    services → tasks → pipeline → vector_store → DocumentChunk → (back to services).
    """
    from documents.tasks import ingest_document  # local import — breaks circular chain

    ingest_document.delay(str(document_id))
    logger.info(
        "Ingestion task dispatched",
        extra={"document_id": str(document_id)},
    )


def mark_document_processing(document_id: uuid.UUID) -> None:
    """Set status to PROCESSING. Called by the Celery task at task start."""
    Document.objects.filter(pk=document_id).update(status=Document.Status.PROCESSING)


def mark_document_ready(document_id: uuid.UUID, chunk_count: int) -> None:
    """Set status to READY with final chunk count. Called on pipeline success."""
    Document.objects.filter(pk=document_id).update(
        status=Document.Status.READY,
        chunk_count=chunk_count,
    )
    logger.info(
        "Document marked ready",
        extra={"document_id": str(document_id), "chunk_count": chunk_count},
    )


def mark_document_failed(document_id: uuid.UUID, error_message: str) -> None:
    """Set status to FAILED with error detail. Called on pipeline exception."""
    Document.objects.filter(pk=document_id).update(
        status=Document.Status.FAILED,
        error_message=error_message,
    )
    logger.error(
        "Document ingestion failed",
        extra={"document_id": str(document_id), "error_message": error_message},
    )


def save_document_chunks(
    document_id: uuid.UUID,
    chunks: list[ChunkData],
    embeddings: list[list[float]],
) -> None:
    """
    Persist a document's chunks and their embeddings to PostgreSQL/pgvector.

    Belongs in the documents service layer — DocumentChunk is a documents model,
    so write operations on it must live here, not in retrieval/.

    Args:
        document_id: UUID of the parent Document row.
        chunks: ChunkData objects produced by the ingestion pipeline.
        embeddings: Embedding vectors, one per chunk (same order as chunks).

    Raises:
        ValueError: if len(chunks) != len(embeddings).
    """
    if len(chunks) != len(embeddings):
        raise ValueError(
            f"chunks ({len(chunks)}) and embeddings ({len(embeddings)}) must have "
            "the same length"
        )

    if not chunks:
        logger.debug(
            "save_document_chunks called with empty list — nothing to persist",
            extra={"document_id": str(document_id)},
        )
        return

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

    # bulk_create writes all rows in a single SQL statement — far fewer round-trips
    # than calling .save() once per chunk, which matters at scale.
    DocumentChunk.objects.bulk_create(chunk_objects, batch_size=500)

    logger.info(
        "Document chunks saved",
        extra={"document_id": str(document_id), "chunk_count": len(chunk_objects)},
    )


def save_bm25_index(document_id: uuid.UUID, bm25_index: BM25Index) -> None:
    """
    Persist a document's BM25 index to Redis with a 7-day TTL.

    Non-fatal on RedisError — keyword search falls back to rebuilding from the DB.
    A warning is logged so the gap is visible in monitoring.

    Redis key: documind:bm25:v1:{document_id}
    TTL: 604800 seconds (7 days)
    """
    redis_key = f"documind:bm25:v1:{document_id}"
    try:
        r = redis_lib.Redis(connection_pool=_get_redis_pool())
        r.setex(redis_key, 604800, bm25_index.serialize())
        logger.info(
            "BM25 index saved to Redis",
            extra={"document_id": str(document_id)},
        )
    except redis_lib.RedisError as e:
        logger.warning(
            "Failed to save BM25 index to Redis — keyword search will rebuild on first query",
            extra={"document_id": str(document_id), "error_type": type(e).__name__},
        )
