"""
documents/services.py — Write operations for the documents app.

Usage:
    from documents.services import create_document, trigger_ingestion
"""

import logging
import uuid

from django.core.files.uploadedfile import UploadedFile

from documents.exceptions import DocumentUploadError
from documents.models import Document

logger = logging.getLogger(__name__)


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
    Document.objects.filter(pk=document_id).update(
        status=Document.Status.PROCESSING
    )


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
