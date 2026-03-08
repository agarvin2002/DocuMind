"""
ingestion/protocols.py — Structural interfaces for ingestion components.

Define parser, chunker, and embedder contracts as typing.Protocol so the
pipeline depends on abstractions, not concrete implementations. Tests can
pass any object that satisfies the protocol without inheriting from a base
class.

Usage:
    from ingestion.protocols import ChunkerProtocol, EmbedderProtocol, ParserProtocol
"""

from pathlib import Path
from typing import IO, Protocol, Union

from ingestion.chunkers import ChunkData


class ParserProtocol(Protocol):
    """Structural interface for document parsers."""

    def parse(self, source: Union[str, Path, IO[bytes]]) -> list[tuple[int, str]]:
        """Extract (1-indexed page_number, text) pairs from a document source."""
        ...


class ChunkerProtocol(Protocol):
    """Structural interface for text chunkers."""

    def chunk(self, pages: list[tuple[int, str]]) -> list[ChunkData]:
        """Split parsed pages into chunks. Returns empty list for blank documents."""
        ...


class EmbedderProtocol(Protocol):
    """Structural interface for embedding generators."""

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts. Returns one vector per input text."""
        ...
