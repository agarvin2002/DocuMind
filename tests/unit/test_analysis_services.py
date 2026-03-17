"""
Unit tests for analysis/services.py and analysis/selectors.py.

Services tests use @pytest.mark.django_db because they write to the database.
Redis calls are mocked with unittest.mock.patch so tests run without a live Redis.
"""

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest

from analysis.exceptions import AnalysisJobNotFoundError
from analysis.models import AnalysisJob
from analysis.selectors import get_cached_result, get_job_by_id, list_jobs
from analysis.services import (
    _cache_job_result,
    create_analysis_job,
    mark_job_complete,
    mark_job_failed,
    mark_job_running,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_job(**kwargs) -> AnalysisJob:
    defaults = {
        "workflow_type": AnalysisJob.WorkflowType.MULTI_HOP,
        "input_data": {"question": "test", "document_ids": []},
    }
    defaults.update(kwargs)
    return AnalysisJob.objects.create(**defaults)


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCreateAnalysisJob:
    def test_returns_pending_job(self):
        job = create_analysis_job(
            workflow_type=AnalysisJob.WorkflowType.MULTI_HOP,
            input_data={"question": "q", "document_ids": []},
        )
        assert job.status == AnalysisJob.Status.PENDING

    def test_stores_input_data(self):
        payload = {"question": "how?", "document_ids": ["abc"]}
        job = create_analysis_job(
            workflow_type=AnalysisJob.WorkflowType.SIMPLE,
            input_data=payload,
        )
        assert job.input_data == payload

    def test_persists_to_database(self):
        job = create_analysis_job(
            workflow_type=AnalysisJob.WorkflowType.COMPARISON,
            input_data={},
        )
        assert AnalysisJob.objects.filter(pk=job.id).exists()


@pytest.mark.django_db
class TestMarkJobRunning:
    def test_sets_status_running(self):
        job = _make_job()
        mark_job_running(job)
        job.refresh_from_db()
        assert job.status == AnalysisJob.Status.RUNNING

    def test_sets_started_at(self):
        job = _make_job()
        assert job.started_at is None
        mark_job_running(job)
        job.refresh_from_db()
        assert job.started_at is not None


@pytest.mark.django_db
class TestMarkJobComplete:
    def test_sets_status_complete(self):
        job = _make_job()
        with patch("analysis.services.redis_lib.Redis"):
            mark_job_complete(job, {"final_answer": "42"})
        job.refresh_from_db()
        assert job.status == AnalysisJob.Status.COMPLETE

    def test_stores_result_data(self):
        job = _make_job()
        result = {"final_answer": "the answer", "citations": []}
        with patch("analysis.services.redis_lib.Redis"):
            mark_job_complete(job, result)
        job.refresh_from_db()
        assert job.result_data == result

    def test_sets_completed_at(self):
        job = _make_job()
        with patch("analysis.services.redis_lib.Redis"):
            mark_job_complete(job, {})
        job.refresh_from_db()
        assert job.completed_at is not None


@pytest.mark.django_db
class TestMarkJobFailed:
    def test_sets_status_failed(self):
        job = _make_job()
        mark_job_failed(job, "something broke")
        job.refresh_from_db()
        assert job.status == AnalysisJob.Status.FAILED

    def test_stores_error_message(self):
        job = _make_job()
        mark_job_failed(job, "LLM timeout")
        job.refresh_from_db()
        assert job.error_message == "LLM timeout"


class TestCacheJobResult:
    def test_writes_json_to_redis(self):
        mock_conn = MagicMock()
        with patch("analysis.services.redis_lib.Redis", return_value=mock_conn):
            _cache_job_result("job-123", {"answer": "42"})
        mock_conn.set.assert_called_once()
        call_args = mock_conn.set.call_args
        assert call_args[0][0] == "documind:agent:result:v1:job-123"
        assert json.loads(call_args[0][1]) == {"answer": "42"}

    def test_redis_failure_is_non_fatal(self):
        with patch("analysis.services.redis_lib.Redis", side_effect=Exception("Redis down")):
            # Must not raise
            _cache_job_result("job-456", {"answer": "42"})


# ---------------------------------------------------------------------------
# Selectors
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestGetJobById:
    def test_returns_existing_job(self):
        job = _make_job()
        result = get_job_by_id(str(job.id))
        assert result.id == job.id

    def test_raises_not_found_for_missing_id(self):
        with pytest.raises(AnalysisJobNotFoundError):
            get_job_by_id(str(uuid.uuid4()))


class TestGetCachedResult:
    def test_returns_dict_on_cache_hit(self):
        mock_conn = MagicMock()
        mock_conn.get.return_value = json.dumps({"answer": "cached"}).encode()
        with patch("analysis.selectors.redis_lib.Redis", return_value=mock_conn):
            result = get_cached_result("job-123")
        assert result == {"answer": "cached"}

    def test_returns_none_on_cache_miss(self):
        mock_conn = MagicMock()
        mock_conn.get.return_value = None
        with patch("analysis.selectors.redis_lib.Redis", return_value=mock_conn):
            result = get_cached_result("job-123")
        assert result is None

    def test_returns_none_on_redis_error(self):
        with patch("analysis.selectors.redis_lib.Redis", side_effect=Exception("Redis down")):
            result = get_cached_result("job-123")
        assert result is None


@pytest.mark.django_db
class TestListJobs:
    def test_returns_all_jobs_when_no_filter(self):
        _make_job()
        _make_job()
        assert list_jobs().count() >= 2

    def test_filters_by_status(self):
        job = _make_job()
        mark_job_failed(job, "err")
        results = list_jobs(status=AnalysisJob.Status.FAILED)
        assert all(j.status == AnalysisJob.Status.FAILED for j in results)
