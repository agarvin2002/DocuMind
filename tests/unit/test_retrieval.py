"""
Unit tests for the retrieval pipeline modules.
No database or Docker required — all external calls are mocked or faked inline.
"""

import uuid
from unittest.mock import MagicMock

from retrieval.bm25 import BM25Index
from retrieval.hybrid import HybridFusion
from retrieval.schemas import ChunkSearchResult

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_result(chunk_id: str, score: float = 0.5) -> ChunkSearchResult:
    """Build a minimal ChunkSearchResult for use in fusion and pipeline tests."""
    return ChunkSearchResult(
        chunk_id=chunk_id,
        document_id="doc-1",
        document_title="Test Doc",
        chunk_index=0,
        child_text=f"text for {chunk_id}",
        parent_text=f"parent text for {chunk_id}",
        page_number=1,
        score=score,
    )


# ---------------------------------------------------------------------------
# BM25Index.search tests
# ---------------------------------------------------------------------------


class TestBM25Search:
    def test_search_returns_matching_positions(self):
        index = BM25Index.build(["hello world", "foo bar", "hello again"])
        results = index.search("hello", k=10)
        positions = [pos for pos, _ in results]
        # "hello" appears in corpus positions 0 and 2 — both should be returned.
        assert 0 in positions
        assert 2 in positions

    def test_search_excludes_non_matching_chunks(self):
        index = BM25Index.build(["hello world", "foo bar", "baz qux"])
        results = index.search("hello", k=10)
        positions = [pos for pos, _ in results]
        # "foo bar" and "baz qux" contain no query term — must not appear.
        assert 1 not in positions
        assert 2 not in positions

    def test_search_results_are_sorted_by_score_descending(self):
        index = BM25Index.build(["hello", "hello hello hello", "world"])
        results = index.search("hello", k=10)
        scores = [score for _, score in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_respects_k_limit(self):
        texts = [f"keyword chunk number {i}" for i in range(20)]
        index = BM25Index.build(texts)
        results = index.search("keyword", k=5)
        assert len(results) <= 5

    def test_search_empty_query_returns_empty(self):
        index = BM25Index.build(["hello world", "foo bar"])
        assert index.search("", k=10) == []

    def test_search_whitespace_only_query_returns_empty(self):
        index = BM25Index.build(["hello world", "foo bar"])
        assert index.search("   ", k=10) == []

    def test_search_returns_list_of_tuples(self):
        index = BM25Index.build(["hello world"])
        results = index.search("hello", k=10)
        assert isinstance(results, list)
        assert all(isinstance(r, tuple) and len(r) == 2 for r in results)

    def test_search_scores_are_nonzero(self):
        index = BM25Index.build(["hello world", "foo bar"])
        results = index.search("hello", k=10)
        assert all(score != 0.0 for _, score in results)


# ---------------------------------------------------------------------------
# HybridFusion tests
# ---------------------------------------------------------------------------


class TestHybridFusion:
    def test_fuse_returns_list_of_chunk_search_results(self):
        fusion = HybridFusion()
        vector = [_make_result("chunk-1")]
        keyword = [_make_result("chunk-2")]
        results = fusion.fuse(vector, keyword)
        assert isinstance(results, list)
        assert all(isinstance(r, ChunkSearchResult) for r in results)

    def test_chunk_in_both_lists_scores_higher_than_single_list(self):
        fusion = HybridFusion()
        # chunk-A appears in both lists at rank 1 — should outscore chunk-B (vector only).
        vector = [_make_result("chunk-A"), _make_result("chunk-B")]
        keyword = [_make_result("chunk-A")]
        results = fusion.fuse(vector, keyword)
        scores = {r.chunk_id: r.score for r in results}
        assert scores["chunk-A"] > scores["chunk-B"]

    def test_fuse_deduplicates_chunk_ids(self):
        fusion = HybridFusion()
        shared = _make_result("chunk-shared")
        results = fusion.fuse([shared], [shared])
        ids = [r.chunk_id for r in results]
        assert ids.count("chunk-shared") == 1

    def test_fuse_both_empty_returns_empty(self):
        assert HybridFusion().fuse([], []) == []

    def test_fuse_only_vector_results(self):
        fusion = HybridFusion()
        results = fusion.fuse([_make_result("chunk-1"), _make_result("chunk-2")], [])
        assert len(results) == 2

    def test_fuse_only_keyword_results(self):
        fusion = HybridFusion()
        results = fusion.fuse([], [_make_result("chunk-1"), _make_result("chunk-2")])
        assert len(results) == 2

    def test_fuse_rrf_score_uses_one_based_rank(self):
        # With k=60 and rank=1: score = 1 / (60 + 1) ≈ 0.01639
        fusion = HybridFusion(k=60)
        results = fusion.fuse([_make_result("chunk-1")], [])
        expected = 1.0 / (60 + 1)
        assert abs(results[0].score - expected) < 1e-9

    def test_fuse_output_is_sorted_by_score_descending(self):
        fusion = HybridFusion()
        vector = [_make_result("a"), _make_result("b"), _make_result("c")]
        keyword = [_make_result("b")]  # "b" appears in both → highest score
        results = fusion.fuse(vector, keyword)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_metadata_prefers_vector_result_when_chunk_in_both_lists(self):
        # Vector result has document_title "Vector Doc", keyword result has "Keyword Doc".
        # Vector metadata should win.
        vector_result = ChunkSearchResult(
            chunk_id="chunk-1",
            document_id="doc-1",
            document_title="Vector Doc",
            chunk_index=0,
            child_text="vector text",
            parent_text="vector parent",
            page_number=1,
            score=0.9,
        )
        keyword_result = ChunkSearchResult(
            chunk_id="chunk-1",
            document_id="doc-1",
            document_title="Keyword Doc",
            chunk_index=0,
            child_text="keyword text",
            parent_text="keyword parent",
            page_number=1,
            score=0.5,
        )
        fusion = HybridFusion()
        results = fusion.fuse([vector_result], [keyword_result])
        assert results[0].document_title == "Vector Doc"
        assert results[0].child_text == "vector text"


# ---------------------------------------------------------------------------
# RetrievalPipeline tests (all dependencies faked via MagicMock)
# ---------------------------------------------------------------------------


class TestRetrievalPipeline:
    def _make_pipeline(
        self,
        embed_return=None,
        vector_return=None,
        keyword_return=None,
        rerank_return=None,
    ):
        """Build a RetrievalPipeline with all dependencies mocked."""
        from retrieval.pipeline import RetrievalPipeline

        embedder = MagicMock()
        embedder.embed_single.return_value = embed_return or [0.1] * 384

        vector_fn = MagicMock(return_value=vector_return or [])
        keyword_fn = MagicMock(return_value=keyword_return or [])

        reranker = MagicMock()
        reranker.rerank.return_value = rerank_return or []

        pipeline = RetrievalPipeline(
            embedder=embedder,
            vector_search_fn=vector_fn,
            keyword_search_fn=keyword_fn,
            reranker=reranker,
        )
        return pipeline, embedder, vector_fn, keyword_fn, reranker

    def test_run_returns_list(self):
        pipeline, *_ = self._make_pipeline(
            rerank_return=[_make_result("chunk-1", score=0.9)]
        )
        results = pipeline.run(query="test", document_id=uuid.uuid4(), k=5)
        assert isinstance(results, list)

    def test_run_calls_embed_single_once(self):
        pipeline, embedder, *_ = self._make_pipeline()
        pipeline.run(query="test query", document_id=uuid.uuid4(), k=5)
        embedder.embed_single.assert_called_once_with("test query")

    def test_run_calls_vector_search_with_candidates_k(self):
        pipeline, _, vector_fn, _, _ = self._make_pipeline()
        doc_id = uuid.uuid4()
        pipeline.run(query="test", document_id=doc_id, k=5)
        # candidates_k = k * candidate_multiplier = 5 * 3 = 15
        _, call_kwargs = vector_fn.call_args
        assert call_kwargs.get("k") == 15 or vector_fn.call_args[0][2] == 15

    def test_run_calls_keyword_search_with_candidates_k(self):
        pipeline, _, _, keyword_fn, _ = self._make_pipeline()
        doc_id = uuid.uuid4()
        pipeline.run(query="test", document_id=doc_id, k=5)
        # candidates_k = k * candidate_multiplier = 5 * 3 = 15
        _, call_kwargs = keyword_fn.call_args
        assert call_kwargs.get("k") == 15 or keyword_fn.call_args[0][2] == 15

    def test_run_slices_to_k_results(self):
        # Reranker returns 6 results but k=3 — pipeline must return only 3.
        many_results = [
            _make_result(f"chunk-{i}", score=float(10 - i)) for i in range(6)
        ]
        pipeline, *_ = self._make_pipeline(rerank_return=many_results)
        results = pipeline.run(query="test", document_id=uuid.uuid4(), k=3)
        assert len(results) == 3

    def test_run_returns_reranker_order(self):
        # Reranker dictates final order — pipeline must not re-sort.
        ordered = [
            _make_result("best", score=0.99),
            _make_result("middle", score=0.55),
            _make_result("worst", score=0.10),
        ]
        pipeline, *_ = self._make_pipeline(rerank_return=ordered)
        results = pipeline.run(query="test", document_id=uuid.uuid4(), k=3)
        assert [r.chunk_id for r in results] == ["best", "middle", "worst"]

    def test_run_returns_empty_when_no_results(self):
        pipeline, *_ = self._make_pipeline(rerank_return=[])
        results = pipeline.run(query="test", document_id=uuid.uuid4(), k=5)
        assert results == []

    def test_run_calls_reranker_with_fused_results(self):
        # Give vector and keyword each one unique result — reranker should see both.
        v_result = _make_result("chunk-v")
        k_result = _make_result("chunk-k")
        pipeline, _, _, _, reranker = self._make_pipeline(
            vector_return=[v_result],
            keyword_return=[k_result],
            rerank_return=[v_result, k_result],
        )
        pipeline.run(query="test", document_id=uuid.uuid4(), k=5)
        call_args = reranker.rerank.call_args
        candidates = call_args[1].get("candidates") or call_args[0][1]
        candidate_ids = {r.chunk_id for r in candidates}
        assert "chunk-v" in candidate_ids
        assert "chunk-k" in candidate_ids


# ---------------------------------------------------------------------------
# CrossEncoderReranker tests
# ---------------------------------------------------------------------------


class TestCrossEncoderReranker:
    def test_score_count_mismatch_raises_reranker_error(self):
        import pytest

        from retrieval.reranker import CrossEncoderReranker, RerankerError

        reranker = CrossEncoderReranker()
        mock_model = MagicMock()
        # predict() returns 1 score for 2 candidates — length mismatch.
        mock_model.predict.return_value = MagicMock(tolist=lambda: [0.9])
        reranker._model = mock_model

        candidates = [_make_result("a"), _make_result("b")]
        with pytest.raises(RerankerError):
            reranker.rerank(query="test", candidates=candidates)

    def test_nan_score_replaced_with_low_value(self):
        # Cross-encoder can return NaN for empty/malformed chunk text.
        # NaN must never reach the JSON serializer — reranker must sanitize it.
        from retrieval.reranker import CrossEncoderReranker

        reranker = CrossEncoderReranker()
        mock_model = MagicMock()
        mock_model.predict.return_value = MagicMock(tolist=lambda: [float("nan"), 5.0])
        reranker._model = mock_model

        candidates = [_make_result("a"), _make_result("b")]
        results = reranker.rerank(query="test", candidates=candidates)

        scores = [r.score for r in results]
        assert all(not (s != s) for s in scores), "NaN scores must be replaced"
        assert scores == sorted(scores, reverse=True), "Results must be sorted highest first"
