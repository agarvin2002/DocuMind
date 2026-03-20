"""
analysis/selectors.py — Read-only queries for the analysis app.

Selectors never write to the database — that is services.py's job.
This separation makes it easy to reason about which code path has side effects.

Usage:
    from analysis.selectors import get_job_by_id
"""

import json
import logging

import redis as redis_lib
from django.conf import settings
from django.db.models import QuerySet

from agents.constants import AGENT_JOB_RESULT_CACHE_PREFIX
from analysis.exceptions import AnalysisJobNotFoundError
from analysis.models import AnalysisJob

logger = logging.getLogger(__name__)

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


def get_job_by_id(job_id: str) -> AnalysisJob:
    """
    Fetch an AnalysisJob by its UUID string from the database.

    Always hits the database. For a Redis-first fast path on completed jobs,
    use get_cached_result() before calling this function.

    Args:
        job_id: UUID string of the job.

    Returns:
        The AnalysisJob instance.

    Raises:
        AnalysisJobNotFoundError: if no job with that ID exists in the DB.
    """
    try:
        return AnalysisJob.objects.get(pk=job_id)
    except AnalysisJob.DoesNotExist:
        raise AnalysisJobNotFoundError()


def get_cached_result(job_id: str) -> dict | None:
    """
    Read a completed job's result_data from Redis.

    Non-fatal: returns None on any error (cache miss, Redis down, bad JSON).
    The caller falls back to the database when None is returned.

    Redis key: AGENT_JOB_RESULT_CACHE_PREFIX + job_id

    Args:
        job_id: UUID string of the job.

    Returns:
        The result dict, or None on a cache miss or error.
    """
    key = f"{AGENT_JOB_RESULT_CACHE_PREFIX}{job_id}"
    try:
        conn = redis_lib.Redis(connection_pool=_get_redis_pool())
        raw = conn.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:  # noqa: BLE001
        logger.warning("agent_result_cache_read_failed", extra={"job_id": job_id})
        return None


def list_jobs(status: str | None = None) -> QuerySet:
    """
    Return a QuerySet of AnalysisJob rows, optionally filtered by status.

    Args:
        status: one of "pending", "running", "complete", "failed" — or None for all.

    Returns:
        Unevaluated Django QuerySet (lazy — no SQL until iterated).
    """
    qs = AnalysisJob.objects.all()
    if status:
        qs = qs.filter(status=status)
    return qs
