"""
Unit tests for analysis/views.py.

Uses Django's APIClient so tests exercise the full request/response cycle
(URL routing → view → serializer → service) without needing real Celery workers.

All external calls (Celery dispatch, document existence check) are mocked.
"""

import uuid
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from analysis.models import AnalysisJob

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def valid_doc_id():
    return str(uuid.uuid4())


def _post_analysis(client, payload):
    return client.post("/api/v1/analysis/", payload, format="json")


# ---------------------------------------------------------------------------
# POST /api/v1/analysis/
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAnalysisJobCreateView:
    def test_post_returns_202_with_job_id(self, client, valid_doc_id):
        with (
            patch("analysis.views.get_document_by_id"),
            patch("analysis.views.dispatch_analysis_task"),
        ):
            resp = _post_analysis(client, {
                "question": "What is the main topic?",
                "document_ids": [valid_doc_id],
            })
        assert resp.status_code == 202
        assert "id" in resp.data
        assert resp.data["status"] == "pending"

    def test_post_without_question_returns_400(self, client, valid_doc_id):
        resp = _post_analysis(client, {"document_ids": [valid_doc_id]})
        assert resp.status_code == 400
        assert "question" in resp.data

    def test_post_without_document_ids_returns_400(self, client):
        resp = _post_analysis(client, {"question": "What?"})
        assert resp.status_code == 400
        assert "document_ids" in resp.data

    def test_post_with_non_uuid_document_id_returns_400(self, client):
        resp = _post_analysis(client, {
            "question": "What?",
            "document_ids": ["not-a-uuid"],
        })
        assert resp.status_code == 400

    def test_post_with_more_than_10_document_ids_returns_400(self, client):
        ids = [str(uuid.uuid4()) for _ in range(11)]
        resp = _post_analysis(client, {"question": "Compare these", "document_ids": ids})
        assert resp.status_code == 400

    def test_post_with_nonexistent_document_id_returns_404(self, client, valid_doc_id):
        from documents.exceptions import DocumentNotFoundError

        with patch("analysis.views.get_document_by_id", side_effect=DocumentNotFoundError()):
            resp = _post_analysis(client, {
                "question": "What?",
                "document_ids": [valid_doc_id],
            })
        assert resp.status_code == 404
        assert "detail" in resp.data

    def test_post_dispatches_celery_task(self, client, valid_doc_id):
        with (
            patch("analysis.views.get_document_by_id"),
            patch("analysis.views.dispatch_analysis_task") as mock_dispatch,
        ):
            _post_analysis(client, {
                "question": "Summarise",
                "document_ids": [valid_doc_id],
            })
        mock_dispatch.assert_called_once()

    def test_post_with_valid_workflow_type_stores_it(self, client, valid_doc_id):
        with (
            patch("analysis.views.get_document_by_id"),
            patch("analysis.views.dispatch_analysis_task"),
        ):
            resp = _post_analysis(client, {
                "question": "Compare",
                "document_ids": [valid_doc_id],
                "workflow_type": "comparison",
            })
        assert resp.status_code == 202
        assert resp.data["workflow_type"] == "comparison"

    def test_post_defaults_to_multi_hop_when_workflow_type_omitted(self, client, valid_doc_id):
        with (
            patch("analysis.views.get_document_by_id"),
            patch("analysis.views.dispatch_analysis_task"),
        ):
            resp = _post_analysis(client, {
                "question": "What are the risks?",
                "document_ids": [valid_doc_id],
            })
        assert resp.status_code == 202
        assert resp.data["workflow_type"] == "multi_hop"


# ---------------------------------------------------------------------------
# GET /api/v1/analysis/{job_id}/
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAnalysisJobDetailView:
    def _create_job(self, **kwargs) -> AnalysisJob:
        defaults = {
            "workflow_type": AnalysisJob.WorkflowType.MULTI_HOP,
            "input_data": {"question": "test"},
        }
        defaults.update(kwargs)
        return AnalysisJob.objects.create(**defaults)

    def test_get_returns_pending_job(self, client):
        job = self._create_job()
        resp = client.get(f"/api/v1/analysis/{job.id}/")
        assert resp.status_code == 200
        assert resp.data["status"] == "pending"

    def test_get_completed_job_includes_result_data(self, client):
        result = {"final_answer": "42", "citations": []}
        job = self._create_job(
            status=AnalysisJob.Status.COMPLETE,
            result_data=result,
        )
        resp = client.get(f"/api/v1/analysis/{job.id}/")
        assert resp.status_code == 200
        assert resp.data["result_data"] == result

    def test_get_failed_job_includes_error_message(self, client):
        job = self._create_job(
            status=AnalysisJob.Status.FAILED,
            error_message="LLM timed out",
        )
        resp = client.get(f"/api/v1/analysis/{job.id}/")
        assert resp.status_code == 200
        assert resp.data["error_message"] == "LLM timed out"

    def test_get_unknown_job_id_returns_404(self, client):
        resp = client.get(f"/api/v1/analysis/{uuid.uuid4()}/")
        assert resp.status_code == 404
        assert "detail" in resp.data

    def test_get_completed_job_served_from_cache(self, client):
        job_id = str(uuid.uuid4())
        cached_response = {"id": job_id, "status": "complete", "result_data": {"final_answer": "cached"}}
        with patch("analysis.views.get_cached_result", return_value=cached_response):
            resp = client.get(f"/api/v1/analysis/{job_id}/")
        assert resp.status_code == 200
        assert resp.data["result_data"]["final_answer"] == "cached"
