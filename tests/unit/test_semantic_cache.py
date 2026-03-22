"""
Unit tests for Task 7.3 — Semantic Caching.

Tests cover:
  - SemanticCachePort is satisfied by FakeSemanticCache
  - SemanticCache.lookup() and store() error handling (non-fatal)
  - execute_ask() cache hit path skips LLM
  - execute_ask() cache miss path stores result
  - FakeSemanticCache satisfies SemanticCachePort
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from unittest.mock import MagicMock, patch

from query.constants import SEMANTIC_CACHE_SIMILARITY_THRESHOLD, SEMANTIC_CACHE_TTL_DAYS
from query.protocols import SemanticCachePort
from query.semantic_cache import SemanticCache
from tests.fakes import FakeSemanticCache

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_similarity_threshold_value():
    assert SEMANTIC_CACHE_SIMILARITY_THRESHOLD == 0.92


def test_ttl_days_value():
    assert SEMANTIC_CACHE_TTL_DAYS == 7


# ---------------------------------------------------------------------------
# FakeSemanticCache satisfies SemanticCachePort
# ---------------------------------------------------------------------------


def test_fake_semantic_cache_satisfies_protocol():
    fake = FakeSemanticCache()
    assert isinstance(fake, SemanticCachePort)


def test_fake_semantic_cache_miss_returns_none():
    fake = FakeSemanticCache(hit_answer=None)
    result = fake.lookup("what is X?", uuid.uuid4())
    assert result is None


def test_fake_semantic_cache_hit_returns_answer():
    answer = {"answer": "X is Y", "citations": []}
    fake = FakeSemanticCache(hit_answer=answer)
    result = fake.lookup("what is X?", uuid.uuid4())
    assert result == answer


def test_fake_semantic_cache_store_records_call():
    fake = FakeSemanticCache()
    doc_id = uuid.uuid4()
    payload = {"answer": "hello", "citations": []}
    fake.store("my query", doc_id, payload)
    assert len(fake.store_calls) == 1
    assert fake.store_calls[0]["query"] == "my query"
    assert fake.store_calls[0]["document_id"] == doc_id
    assert fake.store_calls[0]["answer_json"] == payload


def test_fake_semantic_cache_store_does_not_raise_on_multiple_calls():
    fake = FakeSemanticCache()
    doc_id = uuid.uuid4()
    fake.store("q1", doc_id, {"answer": "a1", "citations": []})
    fake.store("q2", doc_id, {"answer": "a2", "citations": []})
    assert len(fake.store_calls) == 2


# ---------------------------------------------------------------------------
# SemanticCache — lookup() error handling (non-fatal)
# ---------------------------------------------------------------------------


def test_semantic_cache_lookup_returns_none_on_embedder_failure():
    """If embedding the query raises, lookup() must return None (never propagate)."""
    cache = SemanticCache()
    with patch("query.models.SemanticCacheEntry") as _mock_model:
        with patch("query.services._get_embedder") as mock_embedder_factory:
            mock_embedder_factory.return_value.embed_single.side_effect = RuntimeError(
                "GPU crash"
            )
            result = cache.lookup("any query", uuid.uuid4())
    assert result is None


def test_semantic_cache_store_does_not_raise_on_db_failure():
    """If objects.create raises, store() must swallow the error silently."""
    cache = SemanticCache()
    with patch("query.models.SemanticCacheEntry") as mock_model:
        with patch("query.services._get_embedder") as mock_embedder_factory:
            mock_embedder_factory.return_value.embed_single.return_value = [0.0] * 384
            mock_model.objects.create.side_effect = Exception("DB write failed")
            # Must not raise
            cache.store("query", uuid.uuid4(), {"answer": "x", "citations": []})


# ---------------------------------------------------------------------------
# execute_ask() — cache hit path (no LLM call)
# ---------------------------------------------------------------------------


def _collect_sse(gen: Iterator[str]) -> list[str]:
    return list(gen)


def test_execute_ask_cache_hit_yields_sse_without_calling_llm():
    """On a cache hit, execute_ask() must yield SSE events and return without LLM."""
    doc_id = uuid.uuid4()
    cached_answer = {"answer": "cached answer text", "citations": []}
    fake_cache = FakeSemanticCache(hit_answer=cached_answer)

    with (
        patch("query.services._get_semantic_cache", return_value=fake_cache),
        patch("query.services._get_pipeline") as mock_pipeline_factory,
        patch("query.services._resolve_provider") as mock_resolve,
        patch("documents.selectors.get_document_by_id"),
    ):
        mock_resolve.return_value = MagicMock()

        from query.services import execute_ask

        events = _collect_sse(execute_ask(query="what is X?", document_id=doc_id, k=5))

    # Pipeline must not have been called (no retrieval on cache hit)
    mock_pipeline_factory.assert_not_called()

    # Must yield at least 3 SSE events: token, citations, done
    assert len(events) >= 3
    # First event contains the cached answer
    assert "cached answer text" in events[0]
    # Last event is done
    assert "done" in events[-1]


def test_execute_ask_cache_hit_does_not_store_again():
    """A cache hit must not trigger another cache.store() call."""
    doc_id = uuid.uuid4()
    fake_cache = FakeSemanticCache(hit_answer={"answer": "cached", "citations": []})

    with (
        patch("query.services._get_semantic_cache", return_value=fake_cache),
        patch("query.services._resolve_provider") as mock_resolve,
        patch("documents.selectors.get_document_by_id"),
    ):
        mock_resolve.return_value = MagicMock()

        from query.services import execute_ask

        list(execute_ask(query="q", document_id=doc_id, k=5))

    assert len(fake_cache.store_calls) == 0


# ---------------------------------------------------------------------------
# execute_ask() — cache miss path (stores after LLM)
# ---------------------------------------------------------------------------


def test_execute_ask_cache_miss_stores_result():
    """On a cache miss, execute_ask() must call cache.store() after yielding done."""
    from tests.fakes import FakeLLMProvider

    doc_id = uuid.uuid4()
    fake_cache = FakeSemanticCache(hit_answer=None)
    fake_provider = FakeLLMProvider(tokens=["Hello", " world"])

    dummy_chunk = MagicMock()
    dummy_chunk.chunk_id = str(uuid.uuid4())
    dummy_chunk.document_title = "Doc"
    dummy_chunk.page_number = 1
    dummy_chunk.parent_text = "some text"

    with (
        patch("query.services._get_semantic_cache", return_value=fake_cache),
        patch("query.services._resolve_provider", return_value=fake_provider),
        patch("documents.selectors.get_document_by_id"),
        patch("query.services._get_pipeline") as mock_pipeline_factory,
        patch("django.conf.settings") as mock_settings,
    ):
        mock_settings.DOCUMIND_MAX_CONTEXT_TOKENS = 4000
        mock_settings.DOCUMIND_LLM_TEMPERATURE = 0.0
        mock_settings.DOCUMIND_LLM_MAX_TOKENS = 2048
        mock_settings.DOCUMIND_LLM_TIMEOUT_SECONDS = 30
        mock_pipeline_factory.return_value.run.return_value = [dummy_chunk]

        from query.services import execute_ask

        _collect_sse(execute_ask(query="q?", document_id=doc_id, k=5))

    # Store must have been called once after the stream
    assert len(fake_cache.store_calls) == 1
    stored = fake_cache.store_calls[0]
    assert stored["document_id"] == doc_id
    assert "answer" in stored["answer_json"]
