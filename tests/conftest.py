"""
Shared pytest fixtures for the DocuMind test suite.
Fixtures defined here are automatically available to all tests without importing.
"""

import pytest


@pytest.fixture
def sample_text():
    """Short document text for testing chunkers and embedders."""
    return (
        "DocuMind is an AI-native document intelligence system. "
        "It allows users to upload PDF documents and ask questions about them. "
        "The system uses hybrid search combining semantic and keyword retrieval."
    )


@pytest.fixture
def sample_pdf_path(tmp_path):
    """Path to a minimal valid PDF file. Deleted automatically after the test."""
    pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"
    pdf_file = tmp_path / "test_document.pdf"
    pdf_file.write_bytes(pdf_content)
    return pdf_file
