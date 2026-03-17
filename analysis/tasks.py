"""
analysis/tasks.py — Celery task for running the AI agent pipeline.

Usage (called from analysis/services.py):
    current_app.send_task(RUN_ANALYSIS_JOB, args=[str(job.id)])

The task follows the same pattern as documents/tasks.py:
  - Fetch the job from DB
  - Mark it RUNNING
  - Run the agent (may take 30–60 seconds)
  - Mark COMPLETE with result_data, or FAILED with error_message
  - Never let an exception escape — always record the outcome on the job
"""

import logging

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded

from analysis.exceptions import AgentError, AnalysisJobNotFoundError
from analysis.selectors import get_job_by_id
from analysis.services import mark_job_complete, mark_job_failed, mark_job_running
from core.tasks import BaseDocuMindTask

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=0,
    base=BaseDocuMindTask,
    name="analysis.tasks.run_analysis_job",
    soft_time_limit=300,
    time_limit=360,
)
def run_analysis_job(self, job_id_str: str) -> None:
    """
    Run the AI agent pipeline for one AnalysisJob.

    max_retries=0: agent failures are not transient. A failed LLM call or
    retrieval error won't succeed on retry — the user should review and resubmit.

    soft_time_limit=300s (5 min): raises SoftTimeLimitExceeded, which we catch
    and record gracefully. time_limit=360s is the hard kill switch.

    Args:
        job_id_str: UUID string of the AnalysisJob to process.
    """
    logger.info("run_analysis_job_start", extra={"job_id": job_id_str})

    # Step 1: fetch the job — exit silently if it no longer exists (was deleted).
    try:
        job = get_job_by_id(job_id_str)
    except AnalysisJobNotFoundError:
        logger.error("run_analysis_job_not_found", extra={"job_id": job_id_str})
        return

    # Step 2: mark RUNNING so the GET endpoint shows progress immediately.
    mark_job_running(job)

    # Step 3: run the agent. Every outcome is captured on the job record.
    try:
        from agents.executor import run_analysis

        result = run_analysis(job)
        mark_job_complete(job, result)
    except SoftTimeLimitExceeded:
        mark_job_failed(job, "Analysis timed out.")
        logger.error("run_analysis_job_timeout", extra={"job_id": job_id_str})
    except AgentError as exc:
        mark_job_failed(job, str(exc))
    except Exception as exc:
        mark_job_failed(job, f"Unexpected error: {exc}")
        logger.exception("run_analysis_job_unexpected_error", extra={"job_id": job_id_str})
