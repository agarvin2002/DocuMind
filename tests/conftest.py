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
    """
    Path to a minimal PDF with real extractable text. Auto-deleted after test.

    The previous fixture produced a valid but text-free PDF. pypdf parsed it
    successfully but returned empty strings, causing silent test failures.
    fpdf2 generates a proper page with embedded text content.
    """
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(200, 10, "DocuMind is an AI document intelligence system.")
    pdf.ln()
    pdf.cell(200, 10, "It uses hybrid search combining semantic and keyword retrieval.")
    pdf_file = tmp_path / "test_document.pdf"
    pdf.output(str(pdf_file))
    return pdf_file


@pytest.fixture
def sample_pdf_bytes(sample_pdf_path):
    """Raw bytes of the sample PDF — for tests that pass a file-like object."""
    return sample_pdf_path.read_bytes()
