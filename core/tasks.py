"""
core/tasks.py — Shared Celery base task for all DocuMind workers.

Provides structured lifecycle logging on every task so failure/retry/success
events are consistently observable in Datadog without repeating the same
logging boilerplate in each individual task.

Usage:
    from core.tasks import BaseDocuMindTask

    @shared_task(bind=True, base=BaseDocuMindTask)
    def my_task(self, ...):
        ...
"""

import logging
import math

from celery import Task

logger = logging.getLogger(__name__)

# Cap exponential backoff at 5 minutes to prevent indefinite worker stalls.
_MAX_RETRY_COUNTDOWN_SECONDS = 300


class BaseDocuMindTask(Task):
    """
    Base class for all DocuMind Celery tasks.

    Automatically emits structured log entries on task failure, retry, and
    success so every task in the system has consistent observability without
    repeating logging boilerplate.
    """

    abstract = True  # Celery will not register this class as a task itself.

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(
            "Task failed",
            extra={
                "task_name": self.name,
                "task_id": task_id,
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
        )
        super().on_failure(exc, task_id, args, kwargs, einfo)

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning(
            "Task retrying",
            extra={
                "task_name": self.name,
                "task_id": task_id,
                "error": str(exc),
                "error_type": type(exc).__name__,
                "retries": self.request.retries,
            },
        )
        super().on_retry(exc, task_id, args, kwargs, einfo)

    def on_success(self, retval, task_id, args, kwargs):
        logger.debug(
            "Task succeeded",
            extra={"task_name": self.name, "task_id": task_id},
        )
        super().on_success(retval, task_id, args, kwargs)

    @staticmethod
    def get_retry_countdown(attempt_number: int) -> int:
        """
        Return an exponential backoff delay in seconds for the given attempt.

        Uses 2^attempt_number, capped at _MAX_RETRY_COUNTDOWN_SECONDS (5 min)
        to prevent workers from stalling indefinitely on a flaky dependency.

        Examples:
            attempt 0 → 1s, attempt 1 → 2s, attempt 2 → 4s, ..., attempt 9+ → 300s
        """
        return min(int(math.pow(2, attempt_number)), _MAX_RETRY_COUNTDOWN_SECONDS)
