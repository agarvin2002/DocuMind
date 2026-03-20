"""
Unit tests for agents/executor.py.

The compiled graph is mocked so tests run without LLM calls or database access.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

import agents.executor as executor_module
from agents.executor import AgentExecutor, run_analysis
from agents.graph import AgentState
from analysis.exceptions import AgentError
from analysis.models import AnalysisJob

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_job(**kwargs) -> AnalysisJob:
    """Build an unsaved AnalysisJob instance for testing."""
    job = AnalysisJob()
    job.id = uuid.uuid4()
    job.workflow_type = kwargs.get("workflow_type", AnalysisJob.WorkflowType.MULTI_HOP)
    job.input_data = kwargs.get("input_data", {
        "question": "What are the risks?",
        "document_ids": [str(uuid.uuid4())],
        "workflow_type": AnalysisJob.WorkflowType.MULTI_HOP,
    })
    return job


def _fake_final_state(**overrides) -> AgentState:
    state: AgentState = {
        "job_id": "test-job",
        "workflow_type": "multi_hop",
        "question": "What are the risks?",
        "document_ids": ["doc-1"],
        "complexity": "complex",
        "sub_questions": ["q1", "q2"],
        "sub_results": [],
        "retrieved_chunks": [],
        "sub_answers": ["a1", "a2"],
        "final_answer": "The main risks are X and Y.",
        "citations": [{"chunk_id": "c1"}],
        "error": None,
    }
    state.update(overrides)
    return state


# ---------------------------------------------------------------------------
# AgentExecutor unit tests
# ---------------------------------------------------------------------------


class TestAgentExecutor:
    def _make_executor(self, final_state: AgentState | None = None) -> AgentExecutor:
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = final_state or _fake_final_state()
        return AgentExecutor(compiled_graph=mock_graph)

    def test_run_builds_correct_initial_state(self):
        executor = self._make_executor()
        doc_id = str(uuid.uuid4())
        job = _make_job(input_data={
            "question": "Compare these",
            "document_ids": [doc_id],
            "workflow_type": "comparison",
        })
        executor.run(job)
        call_args = executor._graph.invoke.call_args[0][0]
        assert call_args["question"] == "Compare these"
        assert call_args["document_ids"] == [doc_id]
        assert call_args["workflow_type"] == "comparison"
        assert call_args["error"] is None

    def test_run_invokes_graph_with_initial_state(self):
        executor = self._make_executor()
        job = _make_job()
        executor.run(job)
        executor._graph.invoke.assert_called_once()

    def test_run_returns_extracted_result_dict(self):
        final_state = _fake_final_state(final_answer="synthesized answer")
        executor = self._make_executor(final_state)
        result = executor.run(_make_job())
        assert result["final_answer"] == "synthesized answer"
        assert "workflow_type" in result
        assert "question" in result
        assert "sub_questions" in result

    def test_run_raises_agent_error_when_graph_raises(self):
        mock_graph = MagicMock()
        mock_graph.invoke.side_effect = RuntimeError("graph exploded")
        executor = AgentExecutor(compiled_graph=mock_graph)
        with pytest.raises(AgentError, match="Graph execution failed"):
            executor.run(_make_job())

    def test_extract_result_includes_all_expected_keys(self):
        executor = self._make_executor()
        result = executor.run(_make_job())
        for key in ["workflow_type", "question", "final_answer", "sub_questions", "sub_answers", "citations", "error"]:
            assert key in result


class TestLazySingleton:
    def setup_method(self):
        """Reset the module-level singleton before each test."""
        executor_module._executor = None

    def test_singleton_is_none_before_first_call(self):
        assert executor_module._executor is None

    def test_lazy_singleton_only_builds_once(self):
        mock_executor = MagicMock()
        with patch("agents.executor._build_executor", return_value=mock_executor) as mock_build:
            run_analysis.__module__  # just access, not call
            # Trigger two calls through _get_executor
            from agents.executor import _get_executor
            first = _get_executor()
            second = _get_executor()
        assert first is second
        mock_build.assert_called_once()

    def teardown_method(self):
        """Clean up singleton after each test."""
        executor_module._executor = None
