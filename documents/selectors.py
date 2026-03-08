"""
documents/selectors.py — Read-only database queries for the documents app.

Usage:
    from documents.selectors import get_document_by_id, list_documents
"""

import logging
import uuid

from documents.exceptions import DocumentNotFoundError
from documents.models import Document, DocumentChunk

logger = logging.getLogger(__name__)


def get_document_by_id(document_id: uuid.UUID) -> Document:
    """
    Fetch a single Document by primary key.

    Raises:
        DocumentNotFoundError: if no Document with that ID exists.
    """
    try:
        return Document.objects.get(pk=document_id)
    except Document.DoesNotExist:
        raise DocumentNotFoundError(f"Document {document_id} not found")


def list_documents(status: str | None = None):
    """
    Return all Documents, optionally filtered by status.

    Returns a lazy QuerySet so callers can chain further filters if needed.
    """
    qs = Document.objects.all().order_by("-created_at")
    if status is not None:
        qs = qs.filter(status=status)
    return qs


def get_chunks_for_document(document_id: uuid.UUID):
    """
    Return all DocumentChunk rows for a document, ordered by chunk_index.
    """
    return DocumentChunk.objects.filter(document_id=document_id).order_by(
        "chunk_index"
    )
