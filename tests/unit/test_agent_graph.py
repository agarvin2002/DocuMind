"""
Unit tests for agents/graph.py.

Nodes are tested in isolation — called directly with fake planner/retrieval/gen_tool
injected. The full graph invocation tests exercise build_agent_graph() end-to-end
using the same fakes (no real LLM, no real DB).
"""

import uuid
from unittest.mock import MagicMock

from agents.graph import (
    AgentState,
    _route_after_classify,
    _route_after_generate_sub,
    _route_after_plan,
    _route_after_retrieve_sub,
    build_agent_graph,
    classify_query_node,
    comparison_retrieve_node,
    contradiction_detect_node,
    error_node,
    generate_sub_answers_node,
    plan_query_node,
    retrieve_for_subquestion_node,
    simple_passthrough_node,
    synthesize_node,
)
from agents.schemas import ComplexityClassification, QueryDecomposition, SubQueryResult
from analysis.exceptions import PlanningError, RetrievalAgentError, SynthesisError
from retrieval.schemas import ChunkSearchResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_state(**overrides) -> AgentState:
    """Return a minimal valid AgentState for testing."""
    state: AgentState = {
        "job_id": "test-job-id",
        "workflow_type": "multi_hop",
        "question": "What are the main risks?",
        "document_ids": [str(uuid.uuid4())],
        "complexity": "",
        "sub_questions": [],
        "sub_results": [],
        "retrieved_chunks": [],
        "sub_answers": [],
        "final_answer": "",
        "citations": [],
        "error": None,
    }
    state.update(overrides)
    return state


def _make_chunk(text: str = "excerpt", page: int = 1) -> ChunkSearchResult:
    return ChunkSearchResult(
        chunk_id="c1",
        document_id=str(uuid.uuid4()),
        document_title="Doc",
        chunk_index=0,
        child_text=text,
        parent_text=text,
        page_number=page,
        score=0.9,
    )


def _fake_planner(
    *,
    workflow_type: str = "multi_hop",
    complexity: str = "complex",
    sub_questions: list[str] | None = None,
    classify_fails: bool = False,
    decompose_fails: bool = False,
):
    planner = MagicMock()
    if classify_fails:
        planner.classify.side_effect = PlanningError("classify failed")
    else:
        planner.classify.return_value = ComplexityClassification(
            complexity=complexity, workflow_type=workflow_type, reasoning="fake"
        )
    if decompose_fails:
        planner.decompose.side_effect = PlanningError("decompose failed")
    else:
        planner.decompose.return_value = QueryDecomposition(
            sub_questions=sub_questions or ["sub q 1", "sub q 2"],
            reasoning="fake",
        )
    return planner


def _fake_retrieval_tool(
    *,
    chunks: list[ChunkSearchResult] | None = None,
    fails: bool = False,
):
    tool = MagicMock()
    if fails:
        tool.retrieve.side_effect = RetrievalAgentError("retrieval failed")
    else:
        tool.retrieve.return_value = chunks or [_make_chunk()]
    return tool


def _fake_gen_tool(
    *,
    answer: str = "fake answer",
    synthesized: str = "fake synthesized",
    generate_fails: bool = False,
    synthesize_fails: bool = False,
):
    tool = MagicMock()
    if generate_fails:
        tool.generate_answer.side_effect = SynthesisError("generation failed")
    else:
        tool.generate_answer.return_value = answer
    if synthesize_fails:
        tool.synthesize.side_effect = SynthesisError("synthesis failed")
    else:
        tool.synthesize.return_value = synthesized
    return tool


# ---------------------------------------------------------------------------
# Node unit tests
# ---------------------------------------------------------------------------


class TestClassifyQueryNode:
    def test_sets_workflow_type(self):
        state = _base_state()
        result = classify_query_node(state, planner=_fake_planner(workflow_type="comparison"))
        assert result["workflow_type"] == "comparison"
        assert result["complexity"] == "complex"

    def test_sets_error_on_planning_failure(self):
        state = _base_state()
        result = classify_query_node(state, planner=_fake_planner(classify_fails=True))
        assert "error" in result
        assert "classify failed" in result["error"]


class TestPlanQueryNode:
    def test_sets_sub_questions(self):
        state = _base_state()
        result = plan_query_node(
            state, planner=_fake_planner(sub_questions=["q1", "q2", "q3"])
        )
        assert result["sub_questions"] == ["q1", "q2", "q3"]

    def test_sets_error_on_planning_failure(self):
        state = _base_state()
        result = plan_query_node(state, planner=_fake_planner(decompose_fails=True))
        assert "error" in result
        assert "decompose failed" in result["error"]


class TestRetrieveForSubquestionNode:
    def test_populates_sub_results(self):
        state = _base_state(sub_questions=["q1", "q2"])
        chunks = [_make_chunk("text")]
        result = retrieve_for_subquestion_node(
            state, retrieval_tool=_fake_retrieval_tool(chunks=chunks)
        )
        assert len(result["sub_results"]) == 2
        assert isinstance(result["sub_results"][0], SubQueryResult)

    def test_sets_error_on_retrieval_failure(self):
        state = _base_state(sub_questions=["q1"])
        result = retrieve_for_subquestion_node(
            state, retrieval_tool=_fake_retrieval_tool(fails=True)
        )
        assert "error" in result
        assert "retrieval failed" in result["error"]


class TestGenerateSubAnswersNode:
    def test_fills_sub_answers(self):
        sub_results = [
            SubQueryResult(sub_question="q1", document_id="doc1", chunks=[_make_chunk()]),
            SubQueryResult(sub_question="q2", document_id="doc1", chunks=[_make_chunk()]),
        ]
        state = _base_state(sub_results=sub_results)
        result = generate_sub_answers_node(
            state, gen_tool=_fake_gen_tool(answer="the answer")
        )
        assert result["sub_answers"] == ["the answer", "the answer"]

    def test_sets_error_on_generation_failure(self):
        sub_results = [SubQueryResult(sub_question="q1", document_id="doc1")]
        state = _base_state(sub_results=sub_results)
        result = generate_sub_answers_node(
            state, gen_tool=_fake_gen_tool(generate_fails=True)
        )
        assert "error" in result


class TestSynthesizeNode:
    def test_produces_final_answer(self):
        state = _base_state(
            sub_questions=["q1", "q2"],
            sub_answers=["a1", "a2"],
        )
        result = synthesize_node(state, gen_tool=_fake_gen_tool(synthesized="final!"))
        assert result["final_answer"] == "final!"
        assert result["citations"] == []

    def test_sets_error_on_synthesis_failure(self):
        state = _base_state(sub_questions=["q1"], sub_answers=["a1"])
        result = synthesize_node(state, gen_tool=_fake_gen_tool(synthesize_fails=True))
        assert "error" in result


class TestComparisonRetrieveNode:
    def test_retrieves_from_multiple_documents(self):
        doc1, doc2 = str(uuid.uuid4()), str(uuid.uuid4())
        state = _base_state(document_ids=[doc1, doc2])
        chunks = [_make_chunk()]
        result = comparison_retrieve_node(
            state, retrieval_tool=_fake_retrieval_tool(chunks=chunks)
        )
        # One chunk per doc × 2 docs = 2 total
        assert len(result["retrieved_chunks"]) == 2

    def test_sets_error_on_retrieval_failure(self):
        state = _base_state(document_ids=[str(uuid.uuid4())])
        result = comparison_retrieve_node(
            state, retrieval_tool=_fake_retrieval_tool(fails=True)
        )
        assert "error" in result


class TestContradictionDetectNode:
    def test_returns_contradiction_report(self):
        state = _base_state(retrieved_chunks=[_make_chunk()])
        result = contradiction_detect_node(
            state, gen_tool=_fake_gen_tool(answer="No contradictions found.")
        )
        assert result["final_answer"] == "No contradictions found."

    def test_sets_error_on_generation_failure(self):
        state = _base_state(retrieved_chunks=[_make_chunk()])
        result = contradiction_detect_node(
            state, gen_tool=_fake_gen_tool(generate_fails=True)
        )
        assert "error" in result


class TestSimplePassthroughNode:
    def test_returns_answer_and_citations(self):
        state = _base_state()
        result = simple_passthrough_node(
            state,
            retrieval_tool=_fake_retrieval_tool(),
            gen_tool=_fake_gen_tool(answer="simple answer"),
        )
        assert result["final_answer"] == "simple answer"
        assert len(result["citations"]) >= 1
        assert result["citations"][0]["document_title"] == "Doc"

    def test_sets_error_on_retrieval_failure(self):
        state = _base_state()
        result = simple_passthrough_node(
            state,
            retrieval_tool=_fake_retrieval_tool(fails=True),
            gen_tool=_fake_gen_tool(),
        )
        assert "error" in result


class TestErrorNode:
    def test_formats_error_as_final_answer(self):
        state = _base_state(error="LLM timed out")
        result = error_node(state)
        assert "Analysis failed" in result["final_answer"]
        assert "LLM timed out" in result["final_answer"]
        assert result["citations"] == []

    def test_handles_missing_error_gracefully(self):
        state = _base_state(error=None)
        result = error_node(state)
        assert "Analysis failed" in result["final_answer"]


# ---------------------------------------------------------------------------
# Routing function tests
# ---------------------------------------------------------------------------


class TestGraphRouting:
    def test_route_after_classify_returns_plan_for_multi_hop(self):
        state = _base_state(workflow_type="multi_hop", error=None)
        assert _route_after_classify(state) == "plan_query_node"

    def test_route_after_classify_returns_comparison_retrieve(self):
        state = _base_state(workflow_type="comparison", error=None)
        assert _route_after_classify(state) == "comparison_retrieve_node"

    def test_route_after_classify_returns_contradiction_retrieve(self):
        state = _base_state(workflow_type="contradiction", error=None)
        assert _route_after_classify(state) == "contradiction_retrieve_node"

    def test_route_after_classify_returns_simple_passthrough(self):
        state = _base_state(workflow_type="simple", error=None)
        assert _route_after_classify(state) == "simple_passthrough_node"

    def test_route_after_classify_routes_to_error_when_error_set(self):
        state = _base_state(error="something broke")
        assert _route_after_classify(state) == "error_node"

    def test_route_after_plan_routes_to_error_on_error(self):
        assert _route_after_plan(_base_state(error="fail")) == "error_node"

    def test_route_after_plan_routes_to_retrieve_on_success(self):
        assert _route_after_plan(_base_state(error=None)) == "retrieve_for_subquestion_node"

    def test_route_after_retrieve_sub_routes_to_error_on_error(self):
        assert _route_after_retrieve_sub(_base_state(error="fail")) == "error_node"

    def test_route_after_generate_sub_routes_to_error_on_error(self):
        assert _route_after_generate_sub(_base_state(error="fail")) == "error_node"

    def test_route_after_generate_sub_routes_to_synthesize_on_success(self):
        assert _route_after_generate_sub(_base_state(error=None)) == "synthesize_node"


# ---------------------------------------------------------------------------
# Full graph invocation tests (end-to-end with fakes)
# ---------------------------------------------------------------------------


class TestFullGraphInvocation:
    def _build(self, planner, retrieval_tool, gen_tool):
        return build_agent_graph(
            planner=planner,
            retrieval_tool=retrieval_tool,
            gen_tool=gen_tool,
        )

    def test_multi_hop_graph_returns_synthesized_answer(self):
        graph = self._build(
            planner=_fake_planner(workflow_type="multi_hop", sub_questions=["q1", "q2"]),
            retrieval_tool=_fake_retrieval_tool(chunks=[_make_chunk()]),
            gen_tool=_fake_gen_tool(answer="sub answer", synthesized="final synthesis"),
        )
        state = _base_state(workflow_type="multi_hop")
        result = graph.invoke(state)
        assert result["final_answer"] == "final synthesis"
        assert result["error"] is None

    def test_simple_graph_returns_answer(self):
        graph = self._build(
            planner=_fake_planner(workflow_type="simple", complexity="simple"),
            retrieval_tool=_fake_retrieval_tool(chunks=[_make_chunk()]),
            gen_tool=_fake_gen_tool(answer="simple answer"),
        )
        state = _base_state(workflow_type="simple")
        result = graph.invoke(state)
        assert result["final_answer"] == "simple answer"

    def test_graph_routes_to_error_node_when_classify_fails(self):
        graph = self._build(
            planner=_fake_planner(classify_fails=True),
            retrieval_tool=_fake_retrieval_tool(),
            gen_tool=_fake_gen_tool(),
        )
        result = graph.invoke(_base_state())
        assert "Analysis failed" in result["final_answer"]
