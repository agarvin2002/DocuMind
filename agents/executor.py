"""
agents/executor.py — Composition root for the agent pipeline.

AgentExecutor wires all Phase 5 dependencies together and runs the compiled
LangGraph state machine for a given AnalysisJob. This is the single place in
the codebase where all agent components are instantiated and connected.

The executor is created lazily (once per worker process) and cached as a
module-level singleton behind a threading.Lock. This is the same double-checked
locking pattern used in the Redis connection pool — fast path (no lock) for the
common case, locked path only on first construction.

Usage (called by analysis/tasks.py):
    from agents.executor import run_analysis
    result = run_analysis(job)
"""

import logging
import threading

from django.conf import settings

from agents.graph import AgentState, build_agent_graph
from analysis.exceptions import AgentError
from analysis.models import AnalysisJob

logger = logging.getLogger(__name__)

_executor: "AgentExecutor | None" = None
_executor_lock = threading.Lock()


def _get_executor() -> "AgentExecutor":
    """
    Return the singleton AgentExecutor, building it on first call.

    Thread-safe via double-checked locking — the outer check avoids acquiring
    the lock on every call after initialisation (the common case). The inner
    check prevents a race where two threads both pass the outer check before
    either has built the executor.
    """
    global _executor
    if _executor is None:
        with _executor_lock:
            if _executor is None:
                _executor = _build_executor()
    return _executor


def _build_executor() -> "AgentExecutor":
    """
    Instantiate all agent dependencies and compile the LangGraph graph.
    Called exactly once per worker process.

    Provider selection mirrors query/services.py — Ollama takes priority when
    OLLAMA_ENABLED=true (local dev / CI without cloud keys). Falls back to
    OpenAI when running with a real API key in staging/production.
    """
    from agents.query_planner import QueryPlanner
    from agents.tools import GenerationTool, RetrievalTool
    from generation.constants import OLLAMA_DUMMY_API_KEY
    from generation.structured import StructuredLLMClient

    if settings.OLLAMA_ENABLED:
        structured_llm = StructuredLLMClient(
            api_key=OLLAMA_DUMMY_API_KEY,
            model=settings.OLLAMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
        )
        logger.info("agent_executor_using_ollama", extra={"model": settings.OLLAMA_MODEL})
    else:
        structured_llm = StructuredLLMClient(
            api_key=settings.OPENAI_API_KEY,
            model=settings.OPENAI_MODEL,
        )
        logger.info("agent_executor_using_openai", extra={"model": settings.OPENAI_MODEL})
    planner = QueryPlanner(structured_llm=structured_llm)
    retrieval_tool = RetrievalTool()
    gen_tool = GenerationTool(structured_llm=structured_llm)
    compiled_graph = build_agent_graph(
        planner=planner,
        retrieval_tool=retrieval_tool,
        gen_tool=gen_tool,
    )
    logger.info("agent_executor_built")
    return AgentExecutor(compiled_graph=compiled_graph)


class AgentExecutor:
    """
    Runs the compiled LangGraph state machine for a given AnalysisJob.

    Responsibilities:
      - Build the initial AgentState from job.input_data
      - Invoke the compiled graph
      - Extract the result dict from the final state
      - Raise AgentError if the graph itself explodes (should not happen —
        nodes catch their own errors — but belt-and-suspenders)
    """

    def __init__(self, compiled_graph) -> None:
        self._graph = compiled_graph

    def run(self, job: AnalysisJob) -> dict:
        """
        Execute the agent pipeline for job and return a result dict.

        Args:
            job: The AnalysisJob to process (status must be RUNNING before calling).

        Returns:
            Dict suitable for storage in AnalysisJob.result_data.

        Raises:
            AgentError: if the graph engine raises an unexpected exception.
        """
        initial_state = self._build_initial_state(job)
        logger.info(
            "agent_execution_start",
            extra={"job_id": str(job.id), "workflow_type": job.workflow_type},
        )
        try:
            final_state = self._graph.invoke(initial_state)
        except Exception as exc:
            raise AgentError(f"Graph execution failed: {exc}") from exc

        result = self._extract_result(final_state)
        logger.info("agent_execution_complete", extra={"job_id": str(job.id)})
        return result

    def _build_initial_state(self, job: AnalysisJob) -> AgentState:
        data = job.input_data
        return AgentState(
            job_id=str(job.id),
            workflow_type=data.get("workflow_type", AnalysisJob.WorkflowType.MULTI_HOP),
            question=data.get("question", ""),
            document_ids=data.get("document_ids", []),
            complexity="",
            sub_questions=[],
            sub_results=[],
            retrieved_chunks=[],
            sub_answers=[],
            final_answer="",
            citations=[],
            error=None,
        )

    def _extract_result(self, state: AgentState) -> dict:
        return {
            "workflow_type": state["workflow_type"],
            "question": state["question"],
            "final_answer": state["final_answer"],
            "sub_questions": state.get("sub_questions", []),
            "sub_answers": state.get("sub_answers", []),
            "citations": state.get("citations", []),
            "error": state.get("error"),
        }


def run_analysis(job: AnalysisJob) -> dict:
    """
    Public entry point called by analysis/tasks.py.
    Delegates to the singleton AgentExecutor.
    """
    return _get_executor().run(job)
