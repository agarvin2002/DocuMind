"""Unit tests for Document and DocumentChunk models."""

import uuid

from documents.models import Document


class TestDocumentModel:
    """Tests for the Document model — no database required."""

    def test_document_has_uuid_primary_key(self):
        doc = Document(title="Test Doc", original_filename="test.pdf")
        assert isinstance(doc.id, uuid.UUID)

    def test_document_default_status_is_pending(self):
        doc = Document(title="Test Doc", original_filename="test.pdf")
        assert doc.status == Document.Status.PENDING

    def test_document_str_shows_title_and_status(self):
        doc = Document(title="Q3 Report", original_filename="q3.pdf")
        result = str(doc)
        assert "Q3 Report" in result
        assert "pending" in result

    def test_document_status_choices_are_correct(self):
        statuses = [choice[0] for choice in Document.Status.choices]
        assert "pending" in statuses
        assert "processing" in statuses
        assert "ready" in statuses
        assert "failed" in statuses
