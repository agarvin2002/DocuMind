"""
analysis/services.py — Write operations for the analysis app.

Follows the same service/selector split as documents/services.py:
    services  = functions that write to the database or dispatch tasks
    selectors = functions that read from the database (analysis/selectors.py)

Usage:
    from analysis.services import create_analysis_job, dispatch_analysis_task
"""

import json
import logging

import redis as redis_lib
from django.conf import settings
from django.utils import timezone

from analysis.models import AnalysisJob

logger = logging.getLogger(__name__)

# TTL for completed job result in Redis (1 hour). Duplicated from agents/constants.py
# to avoid a circular import at module load time — agents/ is created in Step 5.
_JOB_RESULT_TTL: int = 3600

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


def create_analysis_job(workflow_type: str, input_data: dict) -> AnalysisJob:
    """
    Create and persist a new AnalysisJob with status=PENDING.

    Args:
        workflow_type: one of AnalysisJob.WorkflowType — "multi_hop", "comparison",
                       "contradiction", "simple".
        input_data:    arbitrary dict stored as JSON; typically contains question
                       and document_ids.

    Returns:
        The newly created AnalysisJob instance.
    """
    job = AnalysisJob.objects.create(
        workflow_type=workflow_type,
        input_data=input_data,
    )
    logger.info(
        "analysis_job_created",
        extra={"job_id": str(job.id), "workflow_type": workflow_type},
    )
    return job


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
    _cache_job_result(str(job.id), result_data)
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

    Redis key: documind:agent:result:v1:{job_id}
    TTL: 3600 seconds (1 hour)
    """
    key = f"documind:agent:result:v1:{job_id}"
    try:
        conn = redis_lib.Redis(connection_pool=_get_redis_pool())
        conn.set(key, json.dumps(result_data), ex=_JOB_RESULT_TTL)
    except Exception:  # noqa: BLE001
        logger.warning("agent_result_cache_write_failed", extra={"job_id": job_id})
