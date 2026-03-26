"""
analysis/services.py — Write operations for the analysis app.

Follows the same service/selector split as documents/services.py:
    services  = functions that write to the database or dispatch tasks
    selectors = functions that read from the database (analysis/selectors.py)

Usage:
    from analysis.services import create_analysis_job, dispatch_analysis_task
"""

import hashlib
import json
import logging

from django.utils import timezone

from agents.constants import AGENT_JOB_RESULT_CACHE_PREFIX, AGENT_JOB_RESULT_TTL
from analysis.models import AnalysisJob
from core.redis import get_redis_client

logger = logging.getLogger(__name__)


def _compute_idempotency_key(
    question: str, document_ids: list[str], workflow_type: str
) -> str:
    """
    Compute a stable SHA-256 fingerprint for a job request.

    Sorting document_ids ensures that ["a", "b"] and ["b", "a"] produce the
    same key — clients should not be penalised for different ordering.

    Returns the first 16 hex chars (64-bit prefix) — collision-resistant enough
    for job deduplication while keeping the field compact.
    """
    canonical = json.dumps(
        {
            "question": question,
            "document_ids": sorted(document_ids),
            "workflow_type": workflow_type,
        },
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def create_analysis_job(
    workflow_type: str, input_data: dict
) -> tuple[AnalysisJob, bool]:
    """
    Return an AnalysisJob for this request, creating one only if needed.

    Idempotency: if a PENDING, RUNNING, or COMPLETE job with the same
    (question, document_ids, workflow_type) fingerprint already exists, that
    job is returned unchanged. A new job is created only when no active job
    exists (i.e. the previous attempt failed or this is genuinely new).

    Args:
        workflow_type: one of AnalysisJob.WorkflowType.
        input_data:    dict with "question", "document_ids", "workflow_type".

    Returns:
        (job, created) — created=True when a new row was inserted.
    """
    key = _compute_idempotency_key(
        question=input_data["question"],
        document_ids=input_data["document_ids"],
        workflow_type=workflow_type,
    )

    # Return any active (non-failed) job with the same fingerprint.
    existing = (
        AnalysisJob.objects.filter(
            idempotency_key=key,
            status__in=[
                AnalysisJob.Status.PENDING,
                AnalysisJob.Status.RUNNING,
                AnalysisJob.Status.COMPLETE,
            ],
        )
        .order_by("-created_at")
        .first()
    )
    if existing is not None:
        logger.info(
            "analysis_job_deduplicated",
            extra={"job_id": str(existing.id), "workflow_type": workflow_type},
        )
        return existing, False

    # No active job found — a previous attempt may have failed.
    # Clear the idempotency key on any failed job with this fingerprint so the
    # unique constraint does not block the new attempt.
    AnalysisJob.objects.filter(
        idempotency_key=key, status=AnalysisJob.Status.FAILED
    ).update(idempotency_key=None)

    job = AnalysisJob.objects.create(
        workflow_type=workflow_type,
        input_data=input_data,
        idempotency_key=key,
    )
    logger.info(
        "analysis_job_created",
        extra={"job_id": str(job.id), "workflow_type": workflow_type},
    )
    return job, True


def dispatch_analysis_task(job: AnalysisJob) -> None:
    """
    Send the run_analysis_job Celery task for the given job.

    Local imports break the circular chain:
        services → tasks → executor → graph → (back to services for status updates)

    Args:
        job: The AnalysisJob to process in the background.
    """
    from celery import current_app

    from core.task_names import RUN_ANALYSIS_JOB

    current_app.send_task(RUN_ANALYSIS_JOB, args=[str(job.id)])
    logger.info("analysis_job_dispatched", extra={"job_id": str(job.id)})


def mark_job_running(job: AnalysisJob) -> None:
    """
    Transition a job from PENDING → RUNNING and record when it started.

    Uses update_fields so only the status columns are written — avoids
    accidentally overwriting input_data or result_data if another process
    has changed them between our read and our save.

    Args:
        job: The AnalysisJob instance fetched by the Celery task.
    """
    job.status = AnalysisJob.Status.RUNNING
    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at", "updated_at"])
    logger.info("analysis_job_running", extra={"job_id": str(job.id)})


def mark_job_complete(job: AnalysisJob, result_data: dict) -> None:
    """
    Transition a job to COMPLETE, persist the result, and cache it in Redis.

    The Redis write is non-fatal — if it fails, the result is still safely
    stored in the database. Clients can always fall back to the DB read.

    Args:
        job:         The AnalysisJob instance.
        result_data: The structured result dict from AgentExecutor.run().
    """
    job.status = AnalysisJob.Status.COMPLETE
    job.result_data = result_data
    job.completed_at = timezone.now()
    job.save(update_fields=["status", "result_data", "completed_at", "updated_at"])
    from analysis.serializers import AnalysisJobSerializer

    _cache_job_result(str(job.id), dict(AnalysisJobSerializer(job).data))
    logger.info("analysis_job_complete", extra={"job_id": str(job.id)})


def mark_job_failed(job: AnalysisJob, error_message: str) -> None:
    """
    Transition a job to FAILED and store the error reason for the client to read.

    Args:
        job:           The AnalysisJob instance.
        error_message: Human-readable description of what went wrong.
    """
    job.status = AnalysisJob.Status.FAILED
    job.error_message = error_message
    job.completed_at = timezone.now()
    job.save(update_fields=["status", "error_message", "completed_at", "updated_at"])
    logger.error(
        "analysis_job_failed",
        extra={"job_id": str(job.id), "error": error_message},
    )


def _cache_job_result(job_id: str, result_data: dict) -> None:
    """
    Write the completed job result to Redis for fast GET lookups.

    Non-fatal: any Redis error is swallowed and logged as a warning.
    The selector falls back to the database on a cache miss.

    Redis key: AGENT_JOB_RESULT_CACHE_PREFIX + job_id
    TTL: AGENT_JOB_RESULT_TTL seconds
    """
    key = f"{AGENT_JOB_RESULT_CACHE_PREFIX}{job_id}"
    try:
        conn = get_redis_client()
        conn.set(key, json.dumps(result_data), ex=AGENT_JOB_RESULT_TTL)
    except Exception:  # noqa: BLE001
        logger.warning("agent_result_cache_write_failed", extra={"job_id": job_id})
