"""
agents/graph.py — LangGraph state machine for the agent pipeline.

Each node is a plain Python function: (AgentState, *, deps...) -> dict.
The dict contains only the state fields that changed — LangGraph merges it
into the shared state automatically.

Error handling contract:
    - Nodes never raise exceptions to the graph engine.
    - On failure, a node sets state["error"] = str(exc) and returns.
    - Routing functions check state["error"] and redirect to error_node.
    - error_node formats a user-facing message and the graph terminates cleanly.

Workflow routing (set by classify_query_node):
    simple        → simple_passthrough_node → END
    multi_hop     → plan_query_node → retrieve_for_subquestion_node
                  → generate_sub_answers_node → synthesize_node → END
    comparison    → comparison_retrieve_node → comparison_generate_node → END
    contradiction → contradiction_retrieve_node → contradiction_detect_node → END
"""

import logging
import uuid
from functools import partial
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from agents.constants import (
    AGENT_COMPARISON_K,
    AGENT_RETRIEVAL_K,
    AGENT_SUB_QUESTION_MAX,
)
from agents.protocols import QueryPlannerPort, RetrievalToolPort
from agents.schemas import SubQueryResult
from agents.tools import GenerationTool
from analysis.exceptions import PlanningError, RetrievalAgentError, SynthesisError
from analysis.models import AnalysisJob

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _chunks_to_citations(chunks: list) -> list[dict]:
    """Deduplicated citation list from retrieved chunks, ordered by first appearance."""
    seen: set[tuple] = set()
    citations: list[dict] = []
    for chunk in chunks:
        key = (chunk.document_title, chunk.page_number)
        if key not in seen:
            seen.add(key)
            citations.append({
                "document_title": chunk.document_title,
                "page_number": chunk.page_number,
                "chunk_id": chunk.chunk_id,
            })
    return citations


# ---------------------------------------------------------------------------
# Shared state definition
# ---------------------------------------------------------------------------


class AgentState(TypedDict):
    # Input — set once at entry, never mutated by nodes
    job_id: str
    workflow_type: str
    question: str
    document_ids: list[str]

    # Planner outputs
    complexity: str
    sub_questions: list[str]

    # Retrieval outputs
    sub_results: list[Any]      # list[SubQueryResult]
    retrieved_chunks: list[Any]  # list[ChunkSearchResult] for comparison/contradiction

    # Generation outputs
    sub_answers: list[str]
    final_answer: str
    citations: list[dict]

    # Error state — any node sets this on failure; routing detects it
    error: str | None


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------


def classify_query_node(
    state: AgentState,
    *,
    planner: QueryPlannerPort,
) -> dict:
    """
    Classify the question's complexity and determine the workflow type.
    Sets state["workflow_type"] so routing can direct to the correct path.
    """
    try:
        doc_ids = [uuid.UUID(d) for d in state["document_ids"]]
        result = planner.classify(state["question"], doc_ids)
        logger.info(
            "classify_query_node_complete",
            extra={
                "job_id": state["job_id"],
                "workflow_type": result.workflow_type,
                "complexity": result.complexity,
            },
        )
        return {"workflow_type": result.workflow_type, "complexity": result.complexity}
    except PlanningError as exc:
        logger.error("classify_query_node_failed", extra={"job_id": state["job_id"], "error": str(exc)})
        return {"error": str(exc)}


def plan_query_node(
    state: AgentState,
    *,
    planner: QueryPlannerPort,
) -> dict:
    """
    Decompose the question into sub-questions for multi-hop retrieval.
    """
    try:
        result = planner.decompose(state["question"], n=AGENT_SUB_QUESTION_MAX)
        logger.info(
            "plan_query_node_complete",
            extra={"job_id": state["job_id"], "sub_question_count": len(result.sub_questions)},
        )
        return {"sub_questions": result.sub_questions}
    except PlanningError as exc:
        logger.error("plan_query_node_failed", extra={"job_id": state["job_id"], "error": str(exc)})
        return {"error": str(exc)}


def retrieve_for_subquestion_node(
    state: AgentState,
    *,
    retrieval_tool: RetrievalToolPort,
) -> dict:
    """
    Run retrieval for each sub-question against the first document_id.
    Produces a list of SubQueryResult (one per sub-question).
    """
    sub_results: list[SubQueryResult] = []
    document_id = uuid.UUID(state["document_ids"][0])

    try:
        for sub_q in state["sub_questions"]:
            chunks = retrieval_tool.retrieve(
                query=sub_q,
                document_id=document_id,
                k=AGENT_RETRIEVAL_K,
            )
            sub_results.append(
                SubQueryResult(
                    sub_question=sub_q,
                    document_id=str(document_id),
                    chunks=chunks,
                )
            )
        logger.info(
            "retrieve_for_subquestion_node_complete",
            extra={"job_id": state["job_id"], "sub_result_count": len(sub_results)},
        )
        return {"sub_results": sub_results}
    except RetrievalAgentError as exc:
        logger.error("retrieve_for_subquestion_node_failed", extra={"job_id": state["job_id"], "error": str(exc)})
        return {"error": str(exc)}


def generate_sub_answers_node(
    state: AgentState,
    *,
    gen_tool: GenerationTool,
) -> dict:
    """
    Generate an answer for each sub-question using its retrieved chunks.
    """
    sub_answers: list[str] = []
    try:
        for sub_result in state["sub_results"]:
            answer = gen_tool.generate_answer(
                question=sub_result.sub_question,
                chunks=sub_result.chunks,
                prompt_key="sub_answer",
            )
            sub_result.answer = answer
            sub_answers.append(answer)
        logger.info(
            "generate_sub_answers_node_complete",
            extra={"job_id": state["job_id"], "answer_count": len(sub_answers)},
        )
        return {"sub_answers": sub_answers, "sub_results": state["sub_results"]}
    except SynthesisError as exc:
        logger.error("generate_sub_answers_node_failed", extra={"job_id": state["job_id"], "error": str(exc)})
        return {"error": str(exc)}


def synthesize_node(
    state: AgentState,
    *,
    gen_tool: GenerationTool,
) -> dict:
    """
    Combine all sub-answers into a single unified final answer.
    """
    try:
        final_answer = gen_tool.synthesize(
            original_question=state["question"],
            sub_questions=state["sub_questions"],
            sub_answers=state["sub_answers"],
        )
        all_chunks = [chunk for sr in state["sub_results"] for chunk in sr.chunks]
        logger.info("synthesize_node_complete", extra={"job_id": state["job_id"]})
        return {"final_answer": final_answer, "citations": _chunks_to_citations(all_chunks)}
    except SynthesisError as exc:
        logger.error("synthesize_node_failed", extra={"job_id": state["job_id"], "error": str(exc)})
        return {"error": str(exc)}


def comparison_retrieve_node(
    state: AgentState,
    *,
    retrieval_tool: RetrievalToolPort,
) -> dict:
    """
    Retrieve chunks from every document in scope for comparison.
    All chunks are pooled into retrieved_chunks.
    """
    all_chunks = []
    try:
        for doc_id_str in state["document_ids"]:
            doc_id = uuid.UUID(doc_id_str)
            chunks = retrieval_tool.retrieve(
                query=state["question"],
                document_id=doc_id,
                k=AGENT_COMPARISON_K,
            )
            all_chunks.extend(chunks)
        logger.info(
            "comparison_retrieve_node_complete",
            extra={"job_id": state["job_id"], "total_chunks": len(all_chunks)},
        )
        return {"retrieved_chunks": all_chunks}
    except RetrievalAgentError as exc:
        logger.error("comparison_retrieve_node_failed", extra={"job_id": state["job_id"], "error": str(exc)})
        return {"error": str(exc)}


def comparison_generate_node(
    state: AgentState,
    *,
    gen_tool: GenerationTool,
) -> dict:
    """Generate a structured comparison answer from pooled document chunks."""
    try:
        final_answer = gen_tool.generate_answer(
            question=state["question"],
            chunks=state["retrieved_chunks"],
            prompt_key="comparison",
        )
        logger.info("comparison_generate_node_complete", extra={"job_id": state["job_id"]})
        return {"final_answer": final_answer, "citations": _chunks_to_citations(state["retrieved_chunks"])}
    except SynthesisError as exc:
        logger.error("comparison_generate_node_failed", extra={"job_id": state["job_id"], "error": str(exc)})
        return {"error": str(exc)}


def contradiction_retrieve_node(
    state: AgentState,
    *,
    retrieval_tool: RetrievalToolPort,
) -> dict:
    """
    Retrieve chunks from every document for contradiction detection.
    Same retrieval logic as comparison — different generation prompt follows.
    """
    all_chunks = []
    try:
        for doc_id_str in state["document_ids"]:
            doc_id = uuid.UUID(doc_id_str)
            chunks = retrieval_tool.retrieve(
                query=state["question"],
                document_id=doc_id,
                k=AGENT_COMPARISON_K,
            )
            all_chunks.extend(chunks)
        logger.info(
            "contradiction_retrieve_node_complete",
            extra={"job_id": state["job_id"], "total_chunks": len(all_chunks)},
        )
        return {"retrieved_chunks": all_chunks}
    except RetrievalAgentError as exc:
        logger.error("contradiction_retrieve_node_failed", extra={"job_id": state["job_id"], "error": str(exc)})
        return {"error": str(exc)}


def contradiction_detect_node(
    state: AgentState,
    *,
    gen_tool: GenerationTool,
) -> dict:
    """Detect contradictions across document chunks and return a structured report."""
    try:
        final_answer = gen_tool.generate_answer(
            question=state["question"],
            chunks=state["retrieved_chunks"],
            prompt_key="contradiction_detection",
        )
        logger.info("contradiction_detect_node_complete", extra={"job_id": state["job_id"]})
        return {"final_answer": final_answer, "citations": _chunks_to_citations(state["retrieved_chunks"])}
    except SynthesisError as exc:
        logger.error("contradiction_detect_node_failed", extra={"job_id": state["job_id"], "error": str(exc)})
        return {"error": str(exc)}


def simple_passthrough_node(
    state: AgentState,
    *,
    retrieval_tool: RetrievalToolPort,
    gen_tool: GenerationTool,
) -> dict:
    """
    Single-pass retrieval + generation for simple questions.
    No decomposition or synthesis — one retrieve call, one LLM call.
    """
    try:
        document_id = uuid.UUID(state["document_ids"][0])
        chunks = retrieval_tool.retrieve(
            query=state["question"],
            document_id=document_id,
            k=AGENT_RETRIEVAL_K,
        )
        final_answer = gen_tool.generate_answer(
            question=state["question"],
            chunks=chunks,
            prompt_key="sub_answer",
        )
        logger.info("simple_passthrough_node_complete", extra={"job_id": state["job_id"]})
        return {"final_answer": final_answer, "citations": _chunks_to_citations(chunks)}
    except (RetrievalAgentError, SynthesisError) as exc:
        logger.error("simple_passthrough_node_failed", extra={"job_id": state["job_id"], "error": str(exc)})
        return {"error": str(exc)}


def error_node(state: AgentState) -> dict:
    """
    Terminal error handler. Reached when any preceding node sets state["error"].
    Formats a user-facing message and provides empty citations so the result
    dict is always structurally complete.
    """
    error_msg = state.get("error") or "Unknown agent error"
    logger.error(
        "agent_error_node_reached",
        extra={"job_id": state["job_id"], "error": error_msg},
    )
    return {"final_answer": f"Analysis failed: {error_msg}", "citations": []}


# ---------------------------------------------------------------------------
# Routing functions
# ---------------------------------------------------------------------------


def _route_after_classify(state: AgentState) -> str:
    if state.get("error"):
        return "error_node"
    routes = {
        AnalysisJob.WorkflowType.MULTI_HOP: "plan_query_node",
        AnalysisJob.WorkflowType.COMPARISON: "comparison_retrieve_node",
        AnalysisJob.WorkflowType.CONTRADICTION: "contradiction_retrieve_node",
        AnalysisJob.WorkflowType.SIMPLE: "simple_passthrough_node",
    }
    return routes.get(state.get("workflow_type", ""), "simple_passthrough_node")


def _route_after_plan(state: AgentState) -> str:
    return "error_node" if state.get("error") else "retrieve_for_subquestion_node"


def _route_after_retrieve_sub(state: AgentState) -> str:
    return "error_node" if state.get("error") else "generate_sub_answers_node"


def _route_after_generate_sub(state: AgentState) -> str:
    return "error_node" if state.get("error") else "synthesize_node"


# ---------------------------------------------------------------------------
# Graph factory
# ---------------------------------------------------------------------------


def build_agent_graph(
    planner: QueryPlannerPort,
    retrieval_tool: RetrievalToolPort,
    gen_tool: GenerationTool,
):
    """
    Assemble and compile the LangGraph state machine.

    Called once at startup in agents/executor.py — the compiled graph is cached
    as a singleton so LangGraph's compile step (which validates all edges) only
    runs once per worker process.

    All node dependencies are injected via functools.partial so node functions
    stay pure (no globals, no singletons inside the functions themselves).

    Args:
        planner:        QueryPlanner instance (or any QueryPlannerPort).
        retrieval_tool: RetrievalTool instance (or any RetrievalToolPort).
        gen_tool:       GenerationTool instance.

    Returns:
        A compiled LangGraph state machine ready for .invoke().
    """
    graph = StateGraph(AgentState)

    # Register all nodes with their dependencies injected
    graph.add_node("classify_query_node",          partial(classify_query_node, planner=planner))
    graph.add_node("plan_query_node",              partial(plan_query_node, planner=planner))
    graph.add_node("retrieve_for_subquestion_node", partial(retrieve_for_subquestion_node, retrieval_tool=retrieval_tool))
    graph.add_node("generate_sub_answers_node",    partial(generate_sub_answers_node, gen_tool=gen_tool))
    graph.add_node("synthesize_node",              partial(synthesize_node, gen_tool=gen_tool))
    graph.add_node("comparison_retrieve_node",     partial(comparison_retrieve_node, retrieval_tool=retrieval_tool))
    graph.add_node("comparison_generate_node",     partial(comparison_generate_node, gen_tool=gen_tool))
    graph.add_node("contradiction_retrieve_node",  partial(contradiction_retrieve_node, retrieval_tool=retrieval_tool))
    graph.add_node("contradiction_detect_node",    partial(contradiction_detect_node, gen_tool=gen_tool))
    graph.add_node("simple_passthrough_node",      partial(simple_passthrough_node, retrieval_tool=retrieval_tool, gen_tool=gen_tool))
    graph.add_node("error_node",                   error_node)

    # Entry point
    graph.set_entry_point("classify_query_node")

    # Conditional edges — routing functions decide which node runs next
    graph.add_conditional_edges("classify_query_node",           _route_after_classify)
    graph.add_conditional_edges("plan_query_node",               _route_after_plan)
    graph.add_conditional_edges("retrieve_for_subquestion_node", _route_after_retrieve_sub)
    graph.add_conditional_edges("generate_sub_answers_node",     _route_after_generate_sub)

    # Fixed edges — only one possible next node
    graph.add_edge("synthesize_node",             END)
    graph.add_edge("comparison_retrieve_node",    "comparison_generate_node")
    graph.add_edge("comparison_generate_node",    END)
    graph.add_edge("contradiction_retrieve_node", "contradiction_detect_node")
    graph.add_edge("contradiction_detect_node",   END)
    graph.add_edge("simple_passthrough_node",     END)
    graph.add_edge("error_node",                  END)

    return graph.compile()
