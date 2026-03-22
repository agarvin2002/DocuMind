import uuid

import pytest

from evaluation.exceptions import EvaluationError, MetricComputeError
from evaluation.protocols import RAGScorerPort, RAGSystemPort
from tests.fakes import FakeRAGScorer, FakeRAGSystem


class TestRAGSystemPort:
    def test_fake_satisfies_protocol(self):
        fake = FakeRAGSystem()
        assert isinstance(fake, RAGSystemPort)

    def test_answer_returns_tuple_of_str_and_list(self):
        fake = FakeRAGSystem()
        result = fake.answer("What is RAG?", uuid.uuid4(), k=3)
        assert isinstance(result, tuple)
        assert len(result) == 2
        answer, contexts = result
        assert isinstance(answer, str)
        assert isinstance(contexts, list)

    def test_answer_respects_k_limit(self):
        fake = FakeRAGSystem(contexts=["c1", "c2", "c3", "c4", "c5"])
        _, contexts = fake.answer("question", uuid.uuid4(), k=2)
        assert len(contexts) == 2

    def test_answer_increments_call_count(self):
        fake = FakeRAGSystem()
        fake.answer("q1", uuid.uuid4(), k=3)
        fake.answer("q2", uuid.uuid4(), k=3)
        assert fake.call_count == 2

    def test_answer_raises_when_should_fail(self):
        fake = FakeRAGSystem(should_fail=True)
        with pytest.raises(EvaluationError):
            fake.answer("question", uuid.uuid4(), k=3)

    def test_custom_answer_text_is_returned(self):
        fake = FakeRAGSystem(answer="custom answer text")
        answer, _ = fake.answer("question", uuid.uuid4(), k=3)
        assert answer == "custom answer text"

    def test_custom_contexts_are_returned(self):
        fake = FakeRAGSystem(contexts=["chunk A", "chunk B"])
        _, contexts = fake.answer("question", uuid.uuid4(), k=5)
        assert "chunk A" in contexts
        assert "chunk B" in contexts


class TestRAGScorerPort:
    def test_fake_satisfies_protocol(self):
        fake = FakeRAGScorer()
        assert isinstance(fake, RAGScorerPort)

    def test_score_returns_dict_of_floats(self):
        fake = FakeRAGScorer()
        result = fake.score(
            questions=["q1"],
            answers=["a1"],
            contexts=[["ctx1"]],
            ground_truths=["gt1"],
        )
        assert isinstance(result, dict)
        for key, value in result.items():
            assert isinstance(key, str)
            assert isinstance(value, float)

    def test_score_returns_expected_metric_keys(self):
        fake = FakeRAGScorer()
        result = fake.score(["q"], ["a"], [["c"]], ["gt"])
        assert "faithfulness" in result
        assert "answer_relevancy" in result
        assert "context_recall" in result

    def test_score_increments_call_count(self):
        fake = FakeRAGScorer()
        fake.score(["q"], ["a"], [["c"]], ["gt"])
        fake.score(["q"], ["a"], [["c"]], ["gt"])
        assert fake.call_count == 2

    def test_score_raises_when_should_fail(self):
        fake = FakeRAGScorer(should_fail=True)
        with pytest.raises(MetricComputeError):
            fake.score(["q"], ["a"], [["c"]], ["gt"])

    def test_custom_scores_are_returned(self):
        custom = {
            "faithfulness": 0.99,
            "answer_relevancy": 0.95,
            "context_recall": 0.91,
        }
        fake = FakeRAGScorer(scores=custom)
        result = fake.score(["q"], ["a"], [["c"]], ["gt"])
        assert result == custom
