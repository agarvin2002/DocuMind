"""
agents/query_planner.py — LLM-backed query classification and decomposition.

QueryPlanner is the first node in every agent run. It decides:
  1. classify()  — what kind of workflow does this question need?
  2. decompose() — for complex questions, what are the focused sub-questions?

Both results are cached in Redis so repeated identical questions skip the LLM call.
Cache failures are non-fatal — the planner falls back to calling the LLM directly.

Usage:
    planner = QueryPlanner(structured_llm=StructuredLLMClient(...))
    classification = planner.classify("Compare these two documents", document_ids)
    decomposition  = planner.decompose("What are the main risks?", n=3)
"""

import hashlib
import json
import logging
import uuid

import redis as redis_lib
from django.conf import settings

from agents.constants import (
    AGENT_CACHE_TTL,
    AGENT_CLASSIFY_CACHE_PREFIX,
    AGENT_CLASSIFY_MAX_TOKENS,
    AGENT_DECOMPOSE_CACHE_PREFIX,
    AGENT_DECOMPOSE_MAX_TOKENS,
    AGENT_PLANNER_TEMPERATURE,
    AGENT_SUB_QUESTION_MAX,
)
from agents.protocols import StructuredLLMPort
from agents.schemas import ComplexityClassification, QueryDecomposition
from analysis.exceptions import PlanningError
from generation.prompts import get_agent_prompt

logger = logging.getLogger(__name__)

_redis_pool: redis_lib.ConnectionPool | None = None


def _get_redis_pool() -> redis_lib.ConnectionPool:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis_lib.ConnectionPool.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _redis_pool


def _question_hash(question: str) -> str:
    """Short SHA-256 prefix — used as part of the Redis cache key."""
    return hashlib.sha256(question.encode()).hexdigest()[:16]


class QueryPlanner:
    """
    Classifies query complexity and decomposes complex questions into sub-questions.

    Depends on StructuredLLMPort — accepts any object that satisfies the protocol,
    so tests can inject FakeStructuredLLMClient without touching real LLM APIs.
    """

    def __init__(self, structured_llm: StructuredLLMPort) -> None:
        self._llm = structured_llm

    def classify(
        self,
        question: str,
        document_ids: list[uuid.UUID],
    ) -> ComplexityClassification:
        """
        Classify the question's complexity and select the appropriate workflow.

        Args:
            question:     The user's original question.
            document_ids: Documents in scope — passed for context (count matters
                          for comparison/contradiction detection).

        Returns:
            ComplexityClassification with complexity, workflow_type, and reasoning.

        Raises:
            PlanningError: if the LLM call fails.
        """
        q_hash = _question_hash(question)
        cache_key = AGENT_CLASSIFY_CACHE_PREFIX + q_hash
        cached = self._read_cache(cache_key)
        if cached:
            logger.debug(
                "agent_classify_cache_hit",
                extra={"question_hash": q_hash},
            )
            return ComplexityClassification(**cached)

        try:
            result: ComplexityClassification = self._llm.complete(
                system_prompt=get_agent_prompt("complexity_classifier"),
                user_message=question,
                response_model=ComplexityClassification,
                temperature=AGENT_PLANNER_TEMPERATURE,
                max_tokens=AGENT_CLASSIFY_MAX_TOKENS,
                timeout=settings.AGENT_LLM_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            raise PlanningError(f"Query classification failed: {exc}") from exc

        self._write_cache(cache_key, result.model_dump())
        logger.info(
            "agent_classify_complete",
            extra={
                "complexity": result.complexity,
                "workflow_type": result.workflow_type,
            },
        )
        return result

    def decompose(
        self,
        question: str,
        n: int = AGENT_SUB_QUESTION_MAX,
    ) -> QueryDecomposition:
        """
        Break the question into n focused sub-questions.

        Args:
            question: The complex question to decompose.
            n:        Number of sub-questions to generate.

        Returns:
            QueryDecomposition with sub_questions list and reasoning.

        Raises:
            PlanningError: if the LLM call fails.
        """
        q_hash = _question_hash(question)
        cache_key = AGENT_DECOMPOSE_CACHE_PREFIX + q_hash + f":{n}"
        cached = self._read_cache(cache_key)
        if cached:
            logger.debug(
                "agent_decompose_cache_hit",
                extra={"question_hash": q_hash},
            )
            return QueryDecomposition(**cached)

        system_prompt = get_agent_prompt("query_decomposition").format(n=n)
        try:
            result: QueryDecomposition = self._llm.complete(
                system_prompt=system_prompt,
                user_message=question,
                response_model=QueryDecomposition,
                temperature=AGENT_PLANNER_TEMPERATURE,
                max_tokens=AGENT_DECOMPOSE_MAX_TOKENS,
                timeout=settings.AGENT_LLM_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            raise PlanningError(f"Query decomposition failed: {exc}") from exc

        self._write_cache(cache_key, result.model_dump())
        logger.info(
            "agent_decompose_complete",
            extra={"sub_question_count": len(result.sub_questions)},
        )
        return result

    # ------------------------------------------------------------------
    # Redis helpers — non-fatal in both directions
    # ------------------------------------------------------------------

    def _read_cache(self, key: str) -> dict | None:
        try:
            conn = redis_lib.Redis(connection_pool=_get_redis_pool())
            raw = conn.get(key)
            return json.loads(raw) if raw else None
        except Exception:  # noqa: BLE001
            logger.warning("agent_planner_cache_read_failed", extra={"key": key})
            return None

    def _write_cache(self, key: str, data: dict) -> None:
        try:
            conn = redis_lib.Redis(connection_pool=_get_redis_pool())
            conn.set(key, json.dumps(data), ex=AGENT_CACHE_TTL)
        except Exception:  # noqa: BLE001
            logger.warning("agent_planner_cache_write_failed", extra={"key": key})
