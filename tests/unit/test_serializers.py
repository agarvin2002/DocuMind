"""
Unit tests for documents/serializers.py.
No database or Docker required.
"""

from io import BytesIO
from unittest.mock import MagicMock

from documents.serializers import DocumentUploadSerializer


def _make_file(name: str, size: int, content: bytes = b"data") -> MagicMock:
    """Helper: create a fake uploaded file object."""
    f = MagicMock()
    f.name = name
    f.size = size
    f.read = BytesIO(content).read
    return f


class TestDocumentUploadSerializer:
    def test_valid_pdf_passes_validation(self):
        data = {"title": "My Doc"}
        files = {"file": _make_file("report.pdf", 1024)}
        s = DocumentUploadSerializer(data={**data, **files})
        assert s.is_valid(), s.errors

    def test_rejects_non_pdf_extension(self):
        files = {"file": _make_file("notes.txt", 512)}
        s = DocumentUploadSerializer(data=files)
        assert not s.is_valid()
        assert "file" in s.errors

    def test_rejects_oversized_file(self):
        # 51 MB — over the 50 MB default limit
        files = {"file": _make_file("big.pdf", 51 * 1024 * 1024)}
        s = DocumentUploadSerializer(data=files)
        assert not s.is_valid()
        assert "file" in s.errors

    def test_defaults_title_to_filename_stem(self):
        files = {"file": _make_file("contract.pdf", 1024)}
        s = DocumentUploadSerializer(data=files)
        assert s.is_valid(), s.errors
        assert s.validated_data["title"] == "contract"

    def test_explicit_title_is_preserved(self):
        data = {"title": "My Custom Title", "file": _make_file("doc.pdf", 1024)}
        s = DocumentUploadSerializer(data=data)
        assert s.is_valid(), s.errors
        assert s.validated_data["title"] == "My Custom Title"
