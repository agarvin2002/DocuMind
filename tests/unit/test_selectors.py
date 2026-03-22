"""
Unit tests for documents/selectors.py.
These tests require @pytest.mark.django_db because they call .save() and .get().
"""

import uuid

import pytest

from documents.exceptions import DocumentNotFoundError
from documents.models import Document
from documents.selectors import (
    get_chunks_for_document,
    get_document_by_id,
    list_documents,
)


@pytest.mark.django_db
class TestGetDocumentById:
    def test_returns_document_when_found(self):
        doc = Document.objects.create(
            title="Test Doc",
            original_filename="test.pdf",
            file_type=".pdf",
            file_size=1024,
            status=Document.Status.PENDING,
        )
        result = get_document_by_id(doc.id)
        assert result.id == doc.id

    def test_raises_not_found_for_unknown_id(self):
        with pytest.raises(DocumentNotFoundError):
            get_document_by_id(uuid.uuid4())


@pytest.mark.django_db
class TestListDocuments:
    def test_returns_all_documents(self):
        Document.objects.create(
            title="Doc A",
            original_filename="a.pdf",
            file_type=".pdf",
            file_size=100,
            status=Document.Status.PENDING,
        )
        Document.objects.create(
            title="Doc B",
            original_filename="b.pdf",
            file_type=".pdf",
            file_size=200,
            status=Document.Status.READY,
        )
        assert list_documents().count() >= 2

    def test_filters_by_status(self):
        Document.objects.create(
            title="Pending",
            original_filename="p.pdf",
            file_type=".pdf",
            file_size=100,
            status=Document.Status.PENDING,
        )
        Document.objects.create(
            title="Ready",
            original_filename="r.pdf",
            file_type=".pdf",
            file_size=100,
            status=Document.Status.READY,
        )
        pending = list_documents(status=Document.Status.PENDING)
        assert all(d.status == Document.Status.PENDING for d in pending)


@pytest.mark.django_db
class TestGetChunksForDocument:
    def test_returns_empty_queryset_for_new_document(self):
        doc = Document.objects.create(
            title="No Chunks",
            original_filename="nc.pdf",
            file_type=".pdf",
            file_size=100,
            status=Document.Status.PENDING,
        )
        chunks = get_chunks_for_document(doc.id)
        assert chunks.count() == 0
