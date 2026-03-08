"""
ingestion/parsers.py — Extract text content from uploaded documents.

Usage:
    from ingestion.parsers import get_parser, ParseError

    parser = get_parser(".pdf")
    pages = parser.parse(path_or_file_object)
    # [(1, "page one text"), (2, "page two text"), ...]
"""

import logging
from pathlib import Path
from typing import IO, Union

import pypdf
import pypdf.errors

logger = logging.getLogger(__name__)


class ParseError(Exception):
    """
    Raised when a document cannot be parsed.

    Kept as a plain Python exception (not a Django exception) so this module
    can be imported and tested without Django being configured.
    The task layer in documents/tasks.py translates this to DocumentProcessingError.
    """


class PdfParser:
    """
    Extracts text from PDF files using pypdf.

    Returns one (page_number, text) tuple per page so downstream chunkers
    can track source page provenance without re-reading the file.
    Pages with no extractable text (scanned images, encrypted content)
    are included with empty strings so chunk indices remain stable.
    """

    def parse(self, source: Union[str, Path, IO[bytes]]) -> list[tuple[int, str]]:
        """
        Parse a PDF and return (1-indexed page_number, text) pairs.

        Args:
            source: File path or open binary file-like object.

        Returns:
            List of (page_number, text) tuples, one per page.

        Raises:
            ParseError: if the file is not a valid PDF or cannot be opened.
        """
        try:
            reader = pypdf.PdfReader(source)
        except pypdf.errors.PdfReadError as e:
            raise ParseError(f"Invalid or corrupted PDF: {e}") from e
        except Exception as e:  # noqa: BLE001
            raise ParseError(f"Unexpected error opening PDF: {e}") from e

        pages: list[tuple[int, str]] = []
        for page_number, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception as e:  # noqa: BLE001
                # A single unreadable page should not abort the whole document.
                # Log and continue so the remaining pages are still indexed.
                logger.warning(
                    "Failed to extract text from page — skipping",
                    extra={
                        "page_number": page_number,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )
                text = ""
            pages.append((page_number, text))

        logger.debug(
            "PDF parsed",
            extra={
                "page_count": len(pages),
                "non_empty_pages": sum(1 for _, t in pages if t.strip()),
            },
        )
        return pages


def get_parser(file_type: str) -> PdfParser:
    """
    Return the correct parser for the given file extension.

    Centralising parser selection here means the task layer never contains
    if/elif chains for file-type routing. New parsers are registered here only.

    Args:
        file_type: Extension including leading dot, e.g. ".pdf".

    Raises:
        ParseError: if the file type is not supported.
    """
    parsers: dict[str, PdfParser] = {
        ".pdf": PdfParser(),
    }
    parser = parsers.get(file_type.lower())
    if parser is None:
        raise ParseError(
            f"Unsupported file type: {file_type!r}. Supported: {sorted(parsers)}"
        )
    return parser
