"""
tests/fakes.py — Shared test doubles for the DocuMind test suite.
Importable from any test: from tests.fakes import FakeLLMProvider
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

from generation.llm import AnswerGenerationError


class FakeLLMProvider:
    """
    A test double that satisfies LLMProviderPort.
    Pass tokens= for a successful stream, should_fail=True to raise on every call.
    """

    def __init__(self, tokens: list[str] | None = None, should_fail: bool = False) -> None:
        self._tokens = tokens or ["Hello", " world"]
        self._should_fail = should_fail
        self.call_count = 0

    def stream(
        self,
        system_prompt: str,
        user_message: str,
        *,
        temperature: float,
        max_tokens: int,
        timeout: float,
    ) -> Iterator[str]:
        self.call_count += 1
        if self._should_fail:
            raise AnswerGenerationError("fake provider failure")
        yield from self._tokens


# ---------------------------------------------------------------------------
# Phase 5 — agent pipeline fakes
# ---------------------------------------------------------------------------


class FakeStructuredLLMClient:
    """
    Satisfies agents/protocols.StructuredLLMPort.

    Returns a pre-built instance of response_model on each complete() call.
    Inspect call_count and last_response_model in tests to verify behaviour.
    """

    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.call_count = 0
        self.last_response_model = None

    def complete(
        self,
        system_prompt: str,
        user_message: str,
        response_model: type,
        *,
        temperature: float,
        max_tokens: int,
        timeout: float,
    ) -> object:
        from agents.schemas import (
            ComplexityClassification,
            QueryDecomposition,
            SynthesizedAnswer,
        )

        self.call_count += 1
        self.last_response_model = response_model
        if self.should_fail:
            raise AnswerGenerationError("fake structured llm failure")
        if response_model is ComplexityClassification:
            return ComplexityClassification(
                complexity="complex", workflow_type="multi_hop", reasoning="fake"
            )
        if response_model is QueryDecomposition:
            return QueryDecomposition(
                sub_questions=["sub q 1", "sub q 2"], reasoning="fake"
            )
        if response_model is SynthesizedAnswer:
            return SynthesizedAnswer(answer="fake synthesized answer", key_points=["point 1"])
        # Fallback: try to construct with no args (works for simple models)
        return response_model()

    def generate_text(
        self,
        system_prompt: str,
        user_message: str,
        *,
        temperature: float,
        max_tokens: int,
        timeout: float,
    ) -> str:
        self.call_count += 1
        if self.should_fail:
            raise AnswerGenerationError("fake structured llm failure")
        return "fake generated answer"


class FakeRetrievalTool:
    """
    Satisfies agents/protocols.RetrievalToolPort.

    Returns a preset list of ChunkSearchResult for any query.
    Inspect call_count in tests to verify how many times retrieval was called.
    """

    def __init__(
        self,
        chunks: list | None = None,
        *,
        should_fail: bool = False,
    ) -> None:
        from retrieval.schemas import ChunkSearchResult

        self.chunks: list = chunks or [
            ChunkSearchResult(
                chunk_id="fake-chunk-1",
                document_id=str(uuid.uuid4()),
                document_title="Fake Document",
                chunk_index=0,
                child_text="fake excerpt text",
                parent_text="fake excerpt text",
                page_number=1,
                score=0.9,
            )
        ]
        self.should_fail = should_fail
        self.call_count = 0

    def retrieve(
        self,
        query: str,
        document_id: uuid.UUID,
        k: int,
    ) -> list:
        from analysis.exceptions import RetrievalAgentError

        self.call_count += 1
        if self.should_fail:
            raise RetrievalAgentError("fake retrieval failure")
        return self.chunks[:k]
