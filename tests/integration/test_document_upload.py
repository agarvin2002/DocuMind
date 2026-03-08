"""
Integration tests for the document upload and detail API endpoints.
Requires Docker (PostgreSQL + Redis) to be running.
Celery tasks are run synchronously via CELERY_TASK_ALWAYS_EAGER for these tests.
"""

import uuid
from io import BytesIO

import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def pdf_upload(sample_pdf_bytes):
    """Reusable in-memory PDF file for upload tests."""
    return BytesIO(sample_pdf_bytes)


@pytest.mark.django_db
class TestDocumentUploadEndpoint:
    def test_upload_pdf_returns_201(self, api_client, sample_pdf_bytes):
        pdf = BytesIO(sample_pdf_bytes)
        pdf.name = "test.pdf"
        response = api_client.post(
            "/api/v1/documents/",
            {"file": pdf},
            format="multipart",
        )
        assert response.status_code == 201
        assert "id" in response.data
        assert response.data["status"] == "pending"

    def test_upload_non_pdf_returns_400(self, api_client):
        txt = BytesIO(b"plain text content")
        txt.name = "notes.txt"
        response = api_client.post(
            "/api/v1/documents/",
            {"file": txt},
            format="multipart",
        )
        assert response.status_code == 400

    def test_upload_sets_original_filename(self, api_client, sample_pdf_bytes):
        pdf = BytesIO(sample_pdf_bytes)
        pdf.name = "my_contract.pdf"
        response = api_client.post(
            "/api/v1/documents/",
            {"file": pdf},
            format="multipart",
        )
        assert response.status_code == 201
        assert response.data["original_filename"] == "my_contract.pdf"


@pytest.mark.django_db
class TestDocumentDetailEndpoint:
    def test_get_document_returns_200(self, api_client, sample_pdf_bytes):
        pdf = BytesIO(sample_pdf_bytes)
        pdf.name = "test.pdf"
        upload_response = api_client.post(
            "/api/v1/documents/",
            {"file": pdf},
            format="multipart",
        )
        assert upload_response.status_code == 201
        doc_id = upload_response.data["id"]

        response = api_client.get(f"/api/v1/documents/{doc_id}/")
        assert response.status_code == 200
        assert response.data["id"] == doc_id

    def test_get_nonexistent_document_returns_404(self, api_client):
        response = api_client.get(f"/api/v1/documents/{uuid.uuid4()}/")
        assert response.status_code == 404
