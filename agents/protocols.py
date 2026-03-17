"""
agents/protocols.py — Structural interfaces (Protocols) for the agent pipeline.

Protocols are Python's duck-typing contracts. A class satisfies a Protocol if it
has the right methods with the right signatures — no inheritance needed. This lets
graph nodes depend on the interface, not a specific class, making them trivially
testable with fakes.

Usage:
    def my_node(state: AgentState, *, planner: QueryPlannerPort) -> dict:
        result = planner.classify(state["question"], ...)
        ...
"""

import uuid
from typing import Protocol

from retrieval.schemas import ChunkSearchResult


class StructuredLLMPort(Protocol):
    """
    Non-streaming LLM that returns a validated Pydantic model.
    Satisfied by generation.structured.StructuredLLMClient (real)
    and tests.fakes.FakeStructuredLLMClient (test double).
    """

    def complete(
        self,
        system_prompt: str,
        user_message: str,
        response_model: type,
        *,
        temperature: float,
        max_tokens: int,
        timeout: float,
    ) -> object: ...


class QueryPlannerPort(Protocol):
    """
    Classifies query complexity and decomposes complex queries into sub-questions.
    Satisfied by agents.query_planner.QueryPlanner (real)
    and tests.fakes.FakeQueryPlanner (test double).
    """

    def classify(self, question: str, document_ids: list[uuid.UUID]) -> object: ...

    def decompose(self, question: str, n: int) -> object: ...


class RetrievalToolPort(Protocol):
    """
    Retrieves the top-k relevant chunks for a query from a single document.
    Satisfied by agents.tools.RetrievalTool (real)
    and tests.fakes.FakeRetrievalTool (test double).
    """

    def retrieve(
        self,
        query: str,
        document_id: uuid.UUID,
        k: int,
    ) -> list[ChunkSearchResult]: ...
