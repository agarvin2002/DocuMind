"""
Unit tests for analysis/tasks.py.

run_analysis is mocked — tests verify the task's state machine logic
(pending → running → complete/failed) without running a real agent.
"""

import uuid
from unittest.mock import patch

import pytest

from analysis.models import AnalysisJob
from analysis.tasks import run_analysis_job

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_pending_job() -> AnalysisJob:
    return AnalysisJob.objects.create(
        workflow_type=AnalysisJob.WorkflowType.MULTI_HOP,
        input_data={"question": "test", "document_ids": [], "workflow_type": "multi_hop"},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRunAnalysisJobTask:
    def test_task_marks_job_running_then_complete(self):
        job = _create_pending_job()
        result_data = {"final_answer": "42", "citations": []}

        with patch("agents.executor.run_analysis", return_value=result_data):
            run_analysis_job(str(job.id))

        job.refresh_from_db()
        assert job.status == AnalysisJob.Status.COMPLETE
        assert job.result_data == result_data
        assert job.started_at is not None
        assert job.completed_at is not None

    def test_task_marks_job_failed_on_agent_error(self):
        from analysis.exceptions import AgentError

        job = _create_pending_job()
        with patch("agents.executor.run_analysis", side_effect=AgentError("LLM failed")):
            run_analysis_job(str(job.id))

        job.refresh_from_db()
        assert job.status == AnalysisJob.Status.FAILED
        assert "LLM failed" in job.error_message

    def test_task_marks_job_failed_on_soft_time_limit(self):
        from celery.exceptions import SoftTimeLimitExceeded

        job = _create_pending_job()
        with patch("agents.executor.run_analysis", side_effect=SoftTimeLimitExceeded()):
            run_analysis_job(str(job.id))

        job.refresh_from_db()
        assert job.status == AnalysisJob.Status.FAILED
        assert "timed out" in job.error_message.lower()

    def test_task_marks_job_failed_on_unexpected_exception(self):
        job = _create_pending_job()
        with patch("agents.executor.run_analysis", side_effect=RuntimeError("boom")):
            run_analysis_job(str(job.id))

        job.refresh_from_db()
        assert job.status == AnalysisJob.Status.FAILED
        assert "Unexpected error" in job.error_message

    def test_task_exits_silently_for_unknown_job_id(self):
        unknown_id = str(uuid.uuid4())
        # Must not raise — just logs and returns
        run_analysis_job(unknown_id)
