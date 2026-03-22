import pytest

from evaluation.exceptions import MetricComputeError
from evaluation.metrics import MetricResult, compute_ragas_metrics, passes_thresholds
from tests.fakes import FakeRAGScorer

# --- helpers ---


def _make_batch(n: int = 3):
    return (
        [f"question {i}" for i in range(n)],
        [f"answer {i}" for i in range(n)],
        [[f"context {i}"] for i in range(n)],
        [f"ground truth {i}" for i in range(n)],
    )


# --- passes_thresholds ---


class TestPassesThresholds:
    def test_all_above_thresholds_returns_true(self):
        assert passes_thresholds(0.86, 0.81, 0.76) is True

    def test_exactly_at_thresholds_returns_true(self):
        assert passes_thresholds(0.85, 0.80, 0.75) is True

    def test_faithfulness_below_threshold_returns_false(self):
        assert passes_thresholds(0.84, 0.81, 0.76) is False

    def test_answer_relevancy_below_threshold_returns_false(self):
        assert passes_thresholds(0.86, 0.79, 0.76) is False

    def test_context_recall_below_threshold_returns_false(self):
        assert passes_thresholds(0.86, 0.81, 0.74) is False

    def test_all_zero_returns_false(self):
        assert passes_thresholds(0.0, 0.0, 0.0) is False


# --- compute_ragas_metrics ---


class TestComputeRagasMetrics:
    def test_returns_metric_result(self):
        scorer = FakeRAGScorer()
        questions, answers, contexts, ground_truths = _make_batch()
        result = compute_ragas_metrics(
            questions, answers, contexts, ground_truths, scorer=scorer
        )
        assert isinstance(result, MetricResult)

    def test_scores_match_scorer_output(self):
        scorer = FakeRAGScorer(
            scores={
                "faithfulness": 0.90,
                "answer_relevancy": 0.85,
                "context_recall": 0.80,
            }
        )
        questions, answers, contexts, ground_truths = _make_batch()
        result = compute_ragas_metrics(
            questions, answers, contexts, ground_truths, scorer=scorer
        )
        assert result.faithfulness == 0.90
        assert result.answer_relevancy == 0.85
        assert result.context_recall == 0.80

    def test_sample_count_matches_input_length(self):
        scorer = FakeRAGScorer()
        questions, answers, contexts, ground_truths = _make_batch(n=7)
        result = compute_ragas_metrics(
            questions, answers, contexts, ground_truths, scorer=scorer
        )
        assert result.sample_count == 7

    def test_passed_true_when_all_thresholds_met(self):
        scorer = FakeRAGScorer(
            scores={
                "faithfulness": 0.90,
                "answer_relevancy": 0.85,
                "context_recall": 0.80,
            }
        )
        questions, answers, contexts, ground_truths = _make_batch()
        result = compute_ragas_metrics(
            questions, answers, contexts, ground_truths, scorer=scorer
        )
        assert result.passed is True

    def test_passed_false_when_one_threshold_missed(self):
        scorer = FakeRAGScorer(
            scores={
                "faithfulness": 0.60,
                "answer_relevancy": 0.85,
                "context_recall": 0.80,
            }
        )
        questions, answers, contexts, ground_truths = _make_batch()
        result = compute_ragas_metrics(
            questions, answers, contexts, ground_truths, scorer=scorer
        )
        assert result.passed is False

    def test_scorer_called_once(self):
        scorer = FakeRAGScorer()
        questions, answers, contexts, ground_truths = _make_batch()
        compute_ragas_metrics(
            questions, answers, contexts, ground_truths, scorer=scorer
        )
        assert scorer.call_count == 1

    def test_metric_compute_error_propagates(self):
        scorer = FakeRAGScorer(should_fail=True)
        questions, answers, contexts, ground_truths = _make_batch()
        with pytest.raises(MetricComputeError):
            compute_ragas_metrics(
                questions, answers, contexts, ground_truths, scorer=scorer
            )

    def test_missing_score_key_defaults_to_zero(self):
        scorer = FakeRAGScorer(scores={"faithfulness": 0.90})  # missing other keys
        questions, answers, contexts, ground_truths = _make_batch()
        result = compute_ragas_metrics(
            questions, answers, contexts, ground_truths, scorer=scorer
        )
        assert result.answer_relevancy == 0.0
        assert result.context_recall == 0.0

    def test_scores_are_cast_to_float(self):
        scorer = FakeRAGScorer(
            scores={"faithfulness": 1, "answer_relevancy": 1, "context_recall": 1}
        )
        questions, answers, contexts, ground_truths = _make_batch()
        result = compute_ragas_metrics(
            questions, answers, contexts, ground_truths, scorer=scorer
        )
        assert isinstance(result.faithfulness, float)
        assert isinstance(result.answer_relevancy, float)
        assert isinstance(result.context_recall, float)
