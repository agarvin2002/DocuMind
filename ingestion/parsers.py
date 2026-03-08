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

from core.exceptions import ProcessingError

logger = logging.getLogger(__name__)


class ParseError(ProcessingError):
    """Raised when a document cannot be parsed or produces no extractable text."""


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


class ParserRegistry:
    """
    Class-level registry mapping file extensions to parser instances.

    Parsers register themselves once at module load time via register().
    New file types extend the registry without editing existing code.
    """

    _registry: dict[str, PdfParser] = {}

    @classmethod
    def register(cls, extension: str, parser: PdfParser) -> None:
        """Register a parser for the given lowercase extension (e.g. ".pdf")."""
        cls._registry[extension.lower()] = parser

    @classmethod
    def get(cls, extension: str) -> PdfParser:
        """
        Return the registered parser for the given extension.

        Raises:
            ParseError: if no parser is registered for this extension.
        """
        parser = cls._registry.get(extension.lower())
        if parser is None:
            raise ParseError(
                f"Unsupported file type: {extension!r}. "
                f"Supported: {sorted(cls._registry)}"
            )
        return parser


# Register built-in parsers once at module load time.
ParserRegistry.register(".pdf", PdfParser())


def get_parser(extension: str) -> PdfParser:
    """
    Return the correct parser for the given file extension.

    Delegates to ParserRegistry so new parsers can be added via
    ParserRegistry.register() without editing this function.

    Args:
        extension: Extension including leading dot, e.g. ".pdf".

    Raises:
        ParseError: if the file type is not supported.
    """
    return ParserRegistry.get(extension)
