"""
Unit tests for the ingestion pipeline modules.
No database or Docker required — all external calls are mocked.
"""

import io
import uuid
from unittest.mock import MagicMock

import pytest

from ingestion.chunkers import ChunkData, HierarchicalChunker
from ingestion.parsers import ParseError, PdfParser, get_parser

# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


class TestPdfParser:
    def test_parse_returns_list_of_page_tuples(self, sample_pdf_path):
        pages = PdfParser().parse(sample_pdf_path)
        assert isinstance(pages, list)
        assert all(isinstance(p, tuple) and len(p) == 2 for p in pages)

    def test_first_page_number_is_one_indexed(self, sample_pdf_path):
        pages = PdfParser().parse(sample_pdf_path)
        assert len(pages) >= 1
        assert pages[0][0] == 1

    def test_page_text_is_non_empty_for_real_pdf(self, sample_pdf_path):
        pages = PdfParser().parse(sample_pdf_path)
        combined = " ".join(text for _, text in pages)
        assert combined.strip() != ""

    def test_parse_raises_parse_error_for_invalid_bytes(self):
        with pytest.raises(ParseError):
            PdfParser().parse(io.BytesIO(b"not a real pdf"))

    def test_parse_accepts_file_like_object(self, sample_pdf_bytes):
        pages = PdfParser().parse(io.BytesIO(sample_pdf_bytes))
        assert len(pages) >= 1


class TestGetParser:
    def test_returns_pdf_parser_for_dot_pdf(self):
        assert isinstance(get_parser(".pdf"), PdfParser)

    def test_case_insensitive(self):
        assert isinstance(get_parser(".PDF"), PdfParser)

    def test_raises_parse_error_for_unsupported_type(self):
        with pytest.raises(ParseError):
            get_parser(".docx")


# ---------------------------------------------------------------------------
# Chunker tests
# ---------------------------------------------------------------------------


class TestHierarchicalChunker:
    def test_returns_chunk_data_list(self, sample_text):
        pages = [(1, sample_text)]
        chunks = HierarchicalChunker().chunk(pages)
        assert isinstance(chunks, list)
        assert all(isinstance(c, ChunkData) for c in chunks)

    def test_chunk_index_starts_at_zero(self, sample_text):
        pages = [(1, sample_text)]
        chunks = HierarchicalChunker().chunk(pages)
        assert chunks[0].chunk_index == 0

    def test_child_text_is_shorter_than_parent_text(self, sample_text):
        # Use a long enough text to produce meaningful parent windows
        long_text = (sample_text + " ") * 20
        pages = [(1, long_text)]
        chunks = HierarchicalChunker().chunk(pages)
        assert len(chunks[0].child_text) <= len(chunks[0].parent_text)

    def test_empty_pages_returns_empty_list(self):
        chunks = HierarchicalChunker().chunk([(1, "")])
        assert chunks == []

    def test_page_number_is_preserved(self):
        pages = [(3, "word " * 50)]
        chunks = HierarchicalChunker().chunk(pages)
        assert all(c.page_number == 3 for c in chunks)

    def test_chunk_indices_are_sequential(self, sample_text):
        long_text = (sample_text + " ") * 20
        pages = [(1, long_text)]
        chunks = HierarchicalChunker().chunk(pages)
        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks)))


# ---------------------------------------------------------------------------
# Embedder tests (model loading mocked — avoids 90MB download in CI)
# ---------------------------------------------------------------------------


class TestSentenceTransformerEmbedder:
    def test_embed_batch_returns_correct_count(self):
        from ingestion.embedders import SentenceTransformerEmbedder

        embedder = SentenceTransformerEmbedder()
        mock_model = MagicMock()
        import numpy as np

        mock_model.encode.return_value = np.zeros((3, 384))
        embedder._model = mock_model

        result = embedder.embed_batch(["a", "b", "c"])
        assert len(result) == 3

    def test_embed_batch_returns_384_dimensions(self):
        from ingestion.embedders import SentenceTransformerEmbedder

        embedder = SentenceTransformerEmbedder()
        mock_model = MagicMock()
        import numpy as np

        mock_model.encode.return_value = np.zeros((1, 384))
        embedder._model = mock_model

        result = embedder.embed_batch(["hello world"])
        assert len(result[0]) == 384

    def test_embed_batch_empty_input_returns_empty(self):
        from ingestion.embedders import SentenceTransformerEmbedder

        embedder = SentenceTransformerEmbedder()
        assert embedder.embed_batch([]) == []

    def test_embed_batch_returns_plain_python_lists(self):
        from ingestion.embedders import SentenceTransformerEmbedder

        embedder = SentenceTransformerEmbedder()
        mock_model = MagicMock()
        import numpy as np

        mock_model.encode.return_value = np.zeros((1, 384))
        embedder._model = mock_model

        result = embedder.embed_batch(["test"])
        assert isinstance(result, list)
        assert isinstance(result[0], list)
        assert isinstance(result[0][0], float)


# ---------------------------------------------------------------------------
# BM25 tests
# ---------------------------------------------------------------------------


class TestBM25Index:
    def test_build_from_texts(self):
        from retrieval.bm25 import BM25Index

        index = BM25Index.build(["first text", "second text", "third text"])
        assert index.corpus_size == 3

    def test_serialize_roundtrip(self):
        from retrieval.bm25 import BM25Index

        index = BM25Index.build(["hello world", "foo bar"])
        data = index.serialize()
        restored = BM25Index.from_bytes(data)
        assert restored.corpus_size == 2

    def test_build_raises_on_empty(self):
        from retrieval.bm25 import BM25Index

        with pytest.raises(ValueError):
            BM25Index.build([])


# ---------------------------------------------------------------------------
# Pipeline tests (all external calls mocked)
# ---------------------------------------------------------------------------


class TestIngestionPipeline:
    def test_run_returns_pipeline_result(self, sample_pdf_path):
        from ingestion.pipeline import IngestionPipeline

        mock_chunker = MagicMock()
        mock_chunker.chunk.return_value = [
            ChunkData(
                chunk_index=0,
                child_text="child text",
                parent_text="parent text",
                page_number=1,
            )
        ]

        mock_embedder = MagicMock()
        mock_embedder.embed_batch.return_value = [[0.1] * 384]

        pipeline = IngestionPipeline(chunker=mock_chunker, embedder=mock_embedder)
        result = pipeline.run(
            document_id=uuid.uuid4(),
            file_obj=open(sample_pdf_path, "rb"),
            file_type=".pdf",
        )

        assert result.chunk_count == 1
        assert result.page_count >= 1
        assert len(result.chunks) == 1
        assert len(result.embeddings) == 1

    def test_run_raises_parse_error_on_empty_chunks(self, sample_pdf_path):
        from ingestion.parsers import ParseError
        from ingestion.pipeline import IngestionPipeline

        mock_chunker = MagicMock()
        mock_chunker.chunk.return_value = []

        mock_embedder = MagicMock()

        with pytest.raises(ParseError):
            pipeline = IngestionPipeline(
                chunker=mock_chunker, embedder=mock_embedder
            )
            pipeline.run(
                document_id=uuid.uuid4(),
                file_obj=open(sample_pdf_path, "rb"),
                file_type=".pdf",
            )
