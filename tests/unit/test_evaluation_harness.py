from unittest.mock import MagicMock, patch

import pytest

from evaluation.datasets import EvalSample
from evaluation.exceptions import EvaluationError
from evaluation.harness import (
    EvalHarness,
    EvalResult,
    _compute_improvements,
    _determine_verdict,
)
from evaluation.metrics import MetricResult
from tests.fakes import FakeRAGScorer, FakeRAGSystem

# --- fixtures ---

def _make_sample(n: int = 0, doc_id: str = "") -> EvalSample:
    return EvalSample(
        question=f"question {n}",
        ground_truth=f"ground truth {n}",
        document_id=doc_id,
        document_title="ai_concepts",
        tags=("factual",),
    )


def _make_samples(count: int = 3) -> list[EvalSample]:
    return [_make_sample(i) for i in range(count)]


def _passing_metric() -> MetricResult:
    return MetricResult(faithfulness=0.90, answer_relevancy=0.85, context_recall=0.80, sample_count=3, passed=True)


def _failing_metric() -> MetricResult:
    return MetricResult(faithfulness=0.60, answer_relevancy=0.55, context_recall=0.50, sample_count=3, passed=False)


@pytest.fixture
def harness():
    return EvalHarness(
        full_system=FakeRAGSystem(answer="full answer"),
        baseline=FakeRAGSystem(answer="baseline answer"),
        scorer=FakeRAGScorer(scores={"faithfulness": 0.90, "answer_relevancy": 0.85, "context_recall": 0.80}),
        redis_pool=None,
    )


# --- EvalHarness.run ---

class TestEvalHarnessRun:
    def test_returns_eval_result(self, harness):
        result = harness.run(_make_samples())
        assert isinstance(result, EvalResult)

    def test_verdict_is_pass_or_fail_string(self, harness):
        result = harness.run(_make_samples())
        assert result.verdict in ("PASS", "FAIL")

    def test_dataset_size_matches_samples(self, harness):
        result = harness.run(_make_samples(5))
        assert result.dataset_size == 5

    def test_improvements_pct_has_three_keys(self, harness):
        result = harness.run(_make_samples())
        assert set(result.improvements_pct.keys()) == {"faithfulness", "answer_relevancy", "context_recall"}

    def test_cache_hit_skips_computation(self):
        scorer = FakeRAGScorer()
        harness = EvalHarness(
            full_system=FakeRAGSystem(),
            baseline=FakeRAGSystem(),
            scorer=scorer,
            redis_pool=None,
        )
        samples = _make_samples(2)
        cached_result = EvalResult(
            full_system=_passing_metric(),
            baseline=_failing_metric(),
            improvements_pct={"faithfulness": 50.0, "answer_relevancy": 54.5, "context_recall": 60.0},
            verdict="PASS",
            dataset_size=2,
        )
        with patch.object(harness, "_read_cache", return_value=cached_result):
            result = harness.run(samples, use_cache=True)
        assert result is cached_result
        assert scorer.call_count == 0

    def test_cache_miss_triggers_full_run(self):
        scorer = FakeRAGScorer()
        harness = EvalHarness(
            full_system=FakeRAGSystem(),
            baseline=FakeRAGSystem(),
            scorer=scorer,
            redis_pool=None,
        )
        with patch.object(harness, "_read_cache", return_value=None):
            with patch.object(harness, "_write_cache"):
                harness.run(_make_samples(2), use_cache=True)
        assert scorer.call_count == 2  # once for full system, once for baseline

    def test_use_cache_false_skips_read(self):
        scorer = FakeRAGScorer()
        harness = EvalHarness(
            full_system=FakeRAGSystem(),
            baseline=FakeRAGSystem(),
            scorer=scorer,
            redis_pool=None,
        )
        with patch.object(harness, "_read_cache") as mock_read:
            harness.run(_make_samples(), use_cache=False)
        mock_read.assert_not_called()


# --- _collect_answers ---

class TestCollectAnswers:
    def test_all_samples_fail_raises_evaluation_error(self):
        harness = EvalHarness(
            full_system=FakeRAGSystem(should_fail=True),
            baseline=FakeRAGSystem(),
            scorer=FakeRAGScorer(),
            redis_pool=None,
        )
        with pytest.raises(EvaluationError, match="All samples failed"):
            harness._collect_answers(_make_samples(3), harness._full_system, k=5)

    def test_partial_failure_continues_with_remaining(self):
        call_count = 0

        class PartialFailSystem:
            def answer(self, question, document_id, k):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise ValueError("first sample fails")
                return "answer", ["ctx"]

        harness = EvalHarness(
            full_system=PartialFailSystem(),
            baseline=FakeRAGSystem(),
            scorer=FakeRAGScorer(),
            redis_pool=None,
        )
        results = harness._collect_answers(_make_samples(3), harness._full_system, k=5)
        assert len(results) == 2


# --- _compute_improvements ---

class TestComputeImprovements:
    def test_improvement_calculated_correctly(self):
        full = _passing_metric()  # faithfulness=0.90
        base = MetricResult(faithfulness=0.72, answer_relevancy=0.68, context_recall=0.61, sample_count=3, passed=False)
        imps = _compute_improvements(full, base)
        assert imps["faithfulness"] == pytest.approx(25.0, rel=0.01)

    def test_zero_baseline_returns_zero_improvement(self):
        full = _passing_metric()
        base = MetricResult(faithfulness=0.0, answer_relevancy=0.0, context_recall=0.0, sample_count=3, passed=False)
        imps = _compute_improvements(full, base)
        assert imps["faithfulness"] == 0.0


# --- _determine_verdict ---

class TestDetermineVerdict:
    def test_pass_when_thresholds_met_and_improvement_sufficient(self):
        full = _passing_metric()
        imps = {"faithfulness": 25.0, "answer_relevancy": 25.0, "context_recall": 30.0}
        assert _determine_verdict(full, imps) == "PASS"

    def test_fail_when_absolute_thresholds_not_met(self):
        full = _failing_metric()
        imps = {"faithfulness": 25.0, "answer_relevancy": 25.0, "context_recall": 30.0}
        assert _determine_verdict(full, imps) == "FAIL"

    def test_fail_when_improvement_below_minimum(self):
        full = _passing_metric()
        imps = {"faithfulness": 25.0, "answer_relevancy": 10.0, "context_recall": 30.0}
        assert _determine_verdict(full, imps) == "FAIL"


# --- Redis non-fatal ---

class TestRedisCaching:
    def test_redis_read_failure_is_non_fatal(self):
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.get.side_effect = Exception("Redis connection refused")
        with patch("evaluation.harness.redis_lib.Redis", return_value=mock_conn):
            harness = EvalHarness(
                full_system=FakeRAGSystem(),
                baseline=FakeRAGSystem(),
                scorer=FakeRAGScorer(),
                redis_pool=mock_pool,
            )
            result = harness._read_cache("some-key")
        assert result is None

    def test_redis_write_failure_is_non_fatal(self):
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.set.side_effect = Exception("Redis write failed")
        with patch("evaluation.harness.redis_lib.Redis", return_value=mock_conn):
            harness = EvalHarness(
                full_system=FakeRAGSystem(),
                baseline=FakeRAGSystem(),
                scorer=FakeRAGScorer(),
                redis_pool=mock_pool,
            )
            harness._write_cache("some-key", EvalResult(
                full_system=_passing_metric(),
                baseline=_failing_metric(),
                improvements_pct={},
                verdict="PASS",
                dataset_size=3,
            ))
