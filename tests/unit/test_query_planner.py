"""
Unit tests for agents/query_planner.py.

Uses FakeStructuredLLMClient (inline, since tests/fakes.py isn't written until Step 13)
and mocks Redis to test caching behaviour without a live Redis instance.
"""

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest

from agents.query_planner import QueryPlanner
from agents.schemas import ComplexityClassification, QueryDecomposition
from analysis.exceptions import PlanningError
from generation.llm import AnswerGenerationError

# ---------------------------------------------------------------------------
# Minimal inline fake (full fakes land in Step 13 / tests/fakes.py)
# ---------------------------------------------------------------------------


class _FakeLLM:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.call_count = 0

    def complete(
        self,
        system_prompt,
        user_message,
        response_model,
        *,
        temperature,
        max_tokens,
        timeout,
    ):
        self.call_count += 1
        if self.should_fail:
            raise AnswerGenerationError("fake llm failure")
        if response_model is ComplexityClassification:
            return ComplexityClassification(
                complexity="complex", workflow_type="multi_hop", reasoning="fake"
            )
        if response_model is QueryDecomposition:
            return QueryDecomposition(
                sub_questions=["sub q 1", "sub q 2"], reasoning="fake"
            )
        raise ValueError(f"Unexpected response_model: {response_model}")


def _make_planner(*, should_fail: bool = False):
    return QueryPlanner(structured_llm=_FakeLLM(should_fail=should_fail)), _FakeLLM(
        should_fail=should_fail
    )


def _mock_redis_miss():
    """Return a mock Redis connection that always misses the cache."""
    mock_conn = MagicMock()
    mock_conn.get.return_value = None
    return patch("agents.query_planner.get_redis_client", return_value=mock_conn)


def _mock_redis_hit(data: dict):
    """Return a mock Redis connection that always hits with the given data."""
    mock_conn = MagicMock()
    mock_conn.get.return_value = json.dumps(data).encode()
    return patch("agents.query_planner.get_redis_client", return_value=mock_conn)


# ---------------------------------------------------------------------------
# classify()
# ---------------------------------------------------------------------------


class TestQueryPlannerClassify:
    def test_classify_returns_complexity_classification(self):
        llm = _FakeLLM()
        planner = QueryPlanner(structured_llm=llm)
        with _mock_redis_miss():
            result = planner.classify("What are the main risks?", [uuid.uuid4()])
        assert isinstance(result, ComplexityClassification)
        assert result.workflow_type == "multi_hop"

    def test_classify_calls_llm_on_cache_miss(self):
        llm = _FakeLLM()
        planner = QueryPlanner(structured_llm=llm)
        with _mock_redis_miss():
            planner.classify("What are the main risks?", [uuid.uuid4()])
        assert llm.call_count == 1

    def test_classify_returns_cached_result_without_calling_llm(self):
        llm = _FakeLLM()
        planner = QueryPlanner(structured_llm=llm)
        cached_data = {
            "complexity": "simple",
            "workflow_type": "simple",
            "reasoning": "cached",
        }
        with _mock_redis_hit(cached_data):
            result = planner.classify("Same question?", [uuid.uuid4()])
        assert llm.call_count == 0
        assert result.workflow_type == "simple"
        assert result.complexity == "simple"

    def test_classify_raises_planning_error_on_llm_failure(self):
        llm = _FakeLLM(should_fail=True)
        planner = QueryPlanner(structured_llm=llm)
        with _mock_redis_miss(), pytest.raises(PlanningError):
            planner.classify("What?", [uuid.uuid4()])

    def test_classify_falls_back_to_llm_when_redis_errors(self):
        llm = _FakeLLM()
        planner = QueryPlanner(structured_llm=llm)
        with patch(
            "agents.query_planner.get_redis_client", side_effect=Exception("Redis down")
        ):
            result = planner.classify("What?", [uuid.uuid4()])
        assert isinstance(result, ComplexityClassification)
        assert llm.call_count == 1


# ---------------------------------------------------------------------------
# decompose()
# ---------------------------------------------------------------------------


class TestQueryPlannerDecompose:
    def test_decompose_returns_query_decomposition(self):
        llm = _FakeLLM()
        planner = QueryPlanner(structured_llm=llm)
        with _mock_redis_miss():
            result = planner.decompose(
                "What are the main risks and their impacts?", n=2
            )
        assert isinstance(result, QueryDecomposition)
        assert len(result.sub_questions) == 2

    def test_decompose_calls_llm_on_cache_miss(self):
        llm = _FakeLLM()
        planner = QueryPlanner(structured_llm=llm)
        with _mock_redis_miss():
            planner.decompose("Complex question?", n=3)
        assert llm.call_count == 1

    def test_decompose_returns_cached_result_without_calling_llm(self):
        llm = _FakeLLM()
        planner = QueryPlanner(structured_llm=llm)
        cached_data = {
            "sub_questions": ["cached q 1", "cached q 2"],
            "reasoning": "from cache",
        }
        with _mock_redis_hit(cached_data):
            result = planner.decompose("Any question?", n=2)
        assert llm.call_count == 0
        assert result.sub_questions == ["cached q 1", "cached q 2"]

    def test_decompose_raises_planning_error_on_llm_failure(self):
        llm = _FakeLLM(should_fail=True)
        planner = QueryPlanner(structured_llm=llm)
        with _mock_redis_miss(), pytest.raises(PlanningError):
            planner.decompose("Complex question?")

    def test_decompose_cache_key_includes_n(self):
        """Different n values must produce different cache keys (no cross-contamination)."""
        llm = _FakeLLM()
        planner = QueryPlanner(structured_llm=llm)
        written_keys: list[str] = []

        def capture_set(key, value, ex=None):
            written_keys.append(key)

        mock_conn = MagicMock()
        mock_conn.get.return_value = None
        mock_conn.set.side_effect = capture_set

        with patch("agents.query_planner.get_redis_client", return_value=mock_conn):
            planner.decompose("Same question", n=2)
            planner.decompose("Same question", n=4)

        assert written_keys[0] != written_keys[1]
        assert ":2" in written_keys[0]
        assert ":4" in written_keys[1]
