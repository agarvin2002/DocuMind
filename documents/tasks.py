"""
documents/tasks.py — Celery tasks for asynchronous document ingestion.

Usage (called from services.py):
    ingest_document.delay(str(document_id))
"""

import logging
import uuid

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.core.files.storage import default_storage

from documents.services import (
    mark_document_failed,
    mark_document_processing,
    mark_document_ready,
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=0)
def ingest_document(self, document_id_str: str) -> None:
    """
    Run the full ingestion pipeline for one document.

    max_retries=0: a failed ingestion is surfaced immediately as FAILED rather
    than retried silently. Retrying a corrupt or unparseable file would hit the
    same error every time, misleading users about progress.

    Imports for ingestion modules are local to avoid circular import chains at
    module load time (tasks → pipeline → vector_store → DocumentChunk → services).
    """
    from documents.exceptions import DocumentNotFoundError
    from documents.selectors import get_document_by_id
    from ingestion.pipeline import IngestionPipeline

    document_id = uuid.UUID(document_id_str)
    logger.info(
        "Ingestion task started",
        extra={"document_id": document_id_str},
    )

    mark_document_processing(document_id)

    try:
        document = get_document_by_id(document_id)
        file_type = "." + document.original_filename.rsplit(".", 1)[-1].lower()

        with default_storage.open(document.file.name, "rb") as file_obj:
            pipeline = IngestionPipeline()
            result = pipeline.run(
                document_id=document_id,
                file_obj=file_obj,
                file_type=file_type,
            )

        mark_document_ready(document_id, result.chunk_count)
        logger.info(
            "Ingestion task complete",
            extra={
                "document_id": document_id_str,
                "chunk_count": result.chunk_count,
                "page_count": result.page_count,
            },
        )

    except SoftTimeLimitExceeded:
        # Celery sends this at CELERY_TASK_SOFT_TIME_LIMIT (4 min).
        # Mark FAILED cleanly before the hard kill at CELERY_TASK_TIME_LIMIT (5 min).
        mark_document_failed(document_id, "Ingestion timed out after 4 minutes")
        logger.error(
            "Ingestion task exceeded soft time limit",
            extra={"document_id": document_id_str},
        )

    except DocumentNotFoundError as e:
        mark_document_failed(document_id, str(e))
        logger.error(
            "Document not found during ingestion",
            extra={"document_id": document_id_str, "error": str(e)},
        )

    except Exception as e:  # noqa: BLE001
        mark_document_failed(document_id, str(e))
        logger.error(
            "Ingestion task failed",
            extra={
                "document_id": document_id_str,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )
