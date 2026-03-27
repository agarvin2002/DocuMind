"""
documents/tasks.py — Celery tasks for asynchronous document ingestion.

Usage (called from services.py):
    ingest_document.delay(str(document_id))
"""

import logging
import uuid

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded

from core.tasks import BaseDocuMindTask
from documents.services import (
    mark_document_failed,
    mark_document_processing,
    mark_document_ready,
    mark_document_retrying,
    save_bm25_index,
    save_document_chunks,
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, base=BaseDocuMindTask)
def ingest_document(self, document_id_str: str) -> None:
    """
    Run the full ingestion pipeline for one document.

    Transient infrastructure errors (DB connection blip, S3/MinIO hiccup, Redis
    unavailability) are retried up to 3 times with exponential backoff (30s,
    60s, 120s). Permanent errors — corrupt file, unsupported type, document not
    found, parse failure — fail immediately so users see a clear FAILED status
    rather than waiting through pointless retries.

    Imports for ingestion modules are local to avoid circular import chains at
    module load time (tasks → pipeline → embedders → core.exceptions).
    """
    import psycopg2
    import redis.exceptions as redis_exceptions
    from celery.exceptions import MaxRetriesExceededError

    from core.storage import StorageClient
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

        with StorageClient().download_file(document.file.name) as file_obj:
            pipeline = IngestionPipeline()
            result = pipeline.run(
                document_id=document_id,
                file_obj=file_obj,
                file_type=file_type,
            )

        save_document_chunks(document_id, result.chunks, result.embeddings)
        save_bm25_index(document_id, result.bm25_index)
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
        # Permanent: document was deleted before ingestion could run.
        mark_document_failed(document_id, str(e))
        logger.error(
            "Document not found during ingestion",
            extra={"document_id": document_id_str, "error": str(e)},
        )

    except (
        psycopg2.OperationalError,
        ConnectionError,
        redis_exceptions.ConnectionError,
    ) as exc:
        # Transient: retry with exponential backoff — 30s, 60s, 120s.
        # If all retries are exhausted, mark FAILED so the user sees a clear status.
        try:
            mark_document_retrying(document_id)
            raise self.retry(
                exc=exc,
                countdown=30 * (2 ** self.request.retries),
            )
        except MaxRetriesExceededError:
            mark_document_failed(
                document_id,
                f"Ingestion failed after {self.max_retries} retries: {exc}",
            )
            logger.error(
                "Ingestion task exhausted retries",
                extra={
                    "document_id": document_id_str,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "retries": self.request.retries,
                },
            )

    except Exception as e:  # noqa: BLE001
        # Permanent: corrupt file, parse failure, logic error — no value in retrying.
        mark_document_failed(document_id, str(e))
        logger.error(
            "Ingestion task failed",
            extra={
                "document_id": document_id_str,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )
