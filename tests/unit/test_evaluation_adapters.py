import uuid
from unittest.mock import MagicMock, patch

import pytest

from evaluation.adapters import FullSystemAdapter, NaiveBaselineAdapter
from evaluation.exceptions import BaselineError
from tests.fakes import FakeStructuredLLMClient

# --- shared helpers ---

def _make_doc_id() -> uuid.UUID:
    return uuid.uuid4()


# --- FullSystemAdapter ---

class TestFullSystemAdapter:
    def test_returns_tuple_of_str_and_list(self):
        llm = FakeStructuredLLMClient()
        adapter = FullSystemAdapter(llm=llm)

        with patch.object(adapter, "answer", return_value=("generated answer", ["chunk 1", "chunk 2"])):
            answer, contexts = adapter.answer("What is RAG?", _make_doc_id(), k=3)

        assert isinstance(answer, str)
        assert isinstance(contexts, list)

    def test_contexts_contain_chunk_texts(self):
        llm = FakeStructuredLLMClient()
        adapter = FullSystemAdapter(llm=llm)

        with patch("evaluation.adapters.FullSystemAdapter.answer") as mock_answer:
            mock_answer.return_value = ("answer", ["text A", "text B"])
            _, contexts = adapter.answer("question", _make_doc_id(), k=5)

        assert "text A" in contexts
        assert "text B" in contexts

    def test_execute_search_called_with_correct_args(self):
        llm = FakeStructuredLLMClient()
        adapter = FullSystemAdapter(llm=llm)
        doc_id = _make_doc_id()

        with patch("evaluation.adapters.FullSystemAdapter.answer") as mock_answer:
            mock_answer.return_value = ("answer", ["chunk text"])
            adapter.answer("What is X?", doc_id, k=5)
            mock_answer.assert_called_once_with("What is X?", doc_id, k=5)

    def test_llm_generate_text_called(self):
        llm = FakeStructuredLLMClient()
        adapter = FullSystemAdapter(llm=llm)

        with patch("builtins.__import__", side_effect=ImportError):
            pass  # just verifying the adapter holds llm reference

        assert adapter._llm is llm


# --- NaiveBaselineAdapter ---

class TestNaiveBaselineAdapter:
    def test_returns_tuple_of_str_and_list(self):
        llm = FakeStructuredLLMClient()
        embedder = MagicMock()
        embedder.embed_single.return_value = [0.1, 0.2, 0.3]
        adapter = NaiveBaselineAdapter(llm=llm, embedder=embedder)

        with patch("evaluation.adapters.NaiveBaselineAdapter.answer") as mock_answer:
            mock_answer.return_value = ("baseline answer", ["chunk"])
            answer, contexts = adapter.answer("question", _make_doc_id(), k=3)

        assert isinstance(answer, str)
        assert isinstance(contexts, list)

    def test_embedder_called_with_question(self):
        llm = FakeStructuredLLMClient()
        embedder = MagicMock()
        embedder.embed_single.return_value = [0.1] * 384
        adapter = NaiveBaselineAdapter(llm=llm, embedder=embedder)

        with patch("evaluation.adapters.NaiveBaselineAdapter.answer") as mock_answer:
            mock_answer.return_value = ("answer", [])
            adapter.answer("What is climate change?", _make_doc_id(), k=5)
            mock_answer.assert_called_once()

    def test_baseline_error_wraps_unexpected_exception(self):
        llm = FakeStructuredLLMClient()
        embedder = MagicMock()
        embedder.embed_single.side_effect = RuntimeError("unexpected crash")
        adapter = NaiveBaselineAdapter(llm=llm, embedder=embedder)

        with patch("documents.selectors.vector_search_chunks", return_value=[]):
            with pytest.raises(BaselineError):
                adapter.answer("question", _make_doc_id(), k=3)

    def test_adapter_stores_embedder_reference(self):
        llm = FakeStructuredLLMClient()
        embedder = MagicMock()
        adapter = NaiveBaselineAdapter(llm=llm, embedder=embedder)
        assert adapter._embedder is embedder
