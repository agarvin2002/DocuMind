"""
ingestion/pipeline.py — Orchestrate the full document ingestion sequence.

Usage:
    from ingestion.pipeline import IngestionPipeline

    pipeline = IngestionPipeline()
    result = pipeline.run(document_id=doc.id, file_obj=f, file_type=".pdf")
    # PipelineResult(document_id=..., chunks=[...], embeddings=[...], chunk_count=42, ...)
"""

import logging
import uuid
from dataclasses import dataclass
from typing import IO

from ingestion.chunkers import ChunkData, HierarchicalChunker
from ingestion.embedders import SentenceTransformerEmbedder
from ingestion.parsers import ParseError, get_parser
from ingestion.protocols import ChunkerProtocol, EmbedderProtocol
from retrieval.bm25 import BM25Index

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """
    Returned after a successful ingestion run.

    chunks and embeddings are included so the task layer can persist them
    via documents/services.py without the pipeline owning storage I/O.
    """

    document_id: uuid.UUID
    chunks: list[ChunkData]
    embeddings: list[list[float]]
    chunk_count: int
    page_count: int
    bm25_index: BM25Index


class IngestionPipeline:
    """
    Orchestrates parse → chunk → embed for one document.

    The pipeline is a pure transformation: it receives a file-like object and
    returns a PipelineResult with no side effects. The Celery task layer opens
    the file from storage, calls pipeline.run(), then persists the result.

    Chunker and embedder are injected at construction time so tests can
    substitute lightweight fakes without monkey-patching module globals.
    Production code uses the default instances.
    """

    def __init__(
        self,
        chunker: ChunkerProtocol | None = None,
        embedder: EmbedderProtocol | None = None,
    ) -> None:
        # Defaults are constructed here rather than as argument defaults
        # to avoid instantiating the embedding model at import time.
        self._chunker: ChunkerProtocol = chunker or HierarchicalChunker()
        self._embedder: EmbedderProtocol = embedder or SentenceTransformerEmbedder()

    def run(
        self,
        document_id: uuid.UUID,
        file_obj: IO[bytes],
        file_type: str,
    ) -> PipelineResult:
        """
        Run the full ingestion sequence for one document.

        This method has no Django imports and no database side effects — it
        receives a file-like object and returns a plain dataclass. The Celery
        task layer is responsible for persisting chunks and updating
        Document.status based on success or failure.

        Args:
            document_id: UUID of the Document row (for logging correlation).
            file_obj: Open binary file-like object for the uploaded document.
            file_type: Extension including leading dot, e.g. ".pdf".

        Returns:
            PipelineResult with chunks, embeddings, counts, and BM25 index.

        Raises:
            ParseError: if the file cannot be parsed or produces no text.
            EmbeddingGenerationError: if embedding generation fails.
        """
        logger.info(
            "Ingestion pipeline started",
            extra={"document_id": str(document_id), "file_type": file_type},
        )

        # Step 1 — Parse: extract text by page
        parser = get_parser(file_type)
        pages = parser.parse(file_obj)
        page_count = len(pages)

        logger.debug(
            "Document parsed",
            extra={"document_id": str(document_id), "page_count": page_count},
        )

        # Step 2 — Chunk: split into overlapping child/parent windows
        chunks = self._chunker.chunk(pages)
        if not chunks:
            raise ParseError(
                "Document produced no text chunks — file may be image-only or empty"
            )

        logger.debug(
            "Document chunked",
            extra={"document_id": str(document_id), "chunk_count": len(chunks)},
        )

        # Step 3 — Embed: generate 384-dim vectors for all child texts in one pass
        child_texts = [c.child_text for c in chunks]
        embeddings = self._embedder.embed_batch(child_texts)

        # Step 4 — BM25: build keyword index for exact-match retrieval in Phase 3
        bm25_index = BM25Index.build(child_texts)

        logger.info(
            "Ingestion pipeline complete",
            extra={
                "document_id": str(document_id),
                "chunk_count": len(chunks),
                "page_count": page_count,
            },
        )

        return PipelineResult(
            document_id=document_id,
            chunks=chunks,
            embeddings=embeddings,
            chunk_count=len(chunks),
            page_count=page_count,
            bm25_index=bm25_index,
        )
