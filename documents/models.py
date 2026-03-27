"""
Documents app models.

Document      — one row per uploaded file
DocumentChunk — one text chunk extracted from a document, used by the retrieval system
"""

import uuid

from django.db import models
from pgvector.django import VectorField


class Document(models.Model):
    """
    Represents a single uploaded document.

    Status lifecycle:
      PENDING → PROCESSING → READY
                           → FAILED
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=500)

    # Owning API key — used to enforce per-key document isolation.
    # SET_NULL (not CASCADE) so an API key can be revoked without wiping documents;
    # db_index speeds up the ownership filter on GET /api/v1/documents/{id}/.
    api_key = models.ForeignKey(
        "authentication.APIKey",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents",
        db_index=True,
    )

    # File bytes live in MinIO/S3; only the path is stored here.
    file = models.FileField(upload_to="documents/%Y/%m/")
    original_filename = models.CharField(max_length=500)
    file_type = models.CharField(max_length=50, blank=True)
    file_size = models.PositiveBigIntegerField(default=0)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    error_message = models.TextField(blank=True)
    chunk_count = models.PositiveIntegerField(default=0)
    retry_count = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.status})"


class DocumentChunk(models.Model):
    """
    Represents one text chunk extracted from a Document.

    Parent-child chunking strategy:
    - child_text  (128 tokens) — indexed for retrieval (small = precise matches)
    - parent_text (512 tokens) — sent to the LLM as context (large = richer answer)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="chunks",
    )

    chunk_index = models.PositiveIntegerField()
    child_text = models.TextField()
    parent_text = models.TextField()
    page_number = models.PositiveIntegerField(default=0)

    # 384-dimensional vector produced by sentence-transformers.
    embedding = VectorField(dimensions=384, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["document", "chunk_index"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "chunk_index"],
                name="documents_documentchunk_document_chunk_index_uniq",
            )
        ]

    def __str__(self):
        return f"Chunk {self.chunk_index} of {self.document.title}"
