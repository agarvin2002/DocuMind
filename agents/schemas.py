"""
agents/schemas.py — Data shapes for the agent pipeline.

Two categories:
1. Dataclasses (SubQueryResult) — plain Python containers for intermediate state
   that flows between graph nodes. No validation needed; we control all writes.

2. Pydantic models (ComplexityClassification, QueryDecomposition, etc.) — the
   structured output schemas that Instructor uses to parse LLM responses. These
   ARE validated on instantiation because the LLM is an external system that can
   return unexpected values.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel

from retrieval.schemas import ChunkSearchResult

# ---------------------------------------------------------------------------
# Intermediate state containers (dataclasses)
# ---------------------------------------------------------------------------


@dataclass
class SubQueryResult:
    """Holds one sub-question's retrieval results and generated answer."""

    sub_question: str
    document_id: str
    chunks: list[ChunkSearchResult] = field(default_factory=list)
    answer: str = ""


# ---------------------------------------------------------------------------
# LLM structured output schemas (Pydantic — validated by Instructor)
# ---------------------------------------------------------------------------


class ComplexityClassification(BaseModel):
    """LLM classifies whether a question needs one retrieval pass or multiple."""

    complexity: str      # "simple" | "complex"
    workflow_type: str   # "simple" | "multi_hop" | "comparison" | "contradiction"
    reasoning: str


class QueryDecomposition(BaseModel):
    """LLM breaks a complex question into focused sub-questions."""

    sub_questions: list[str]
    reasoning: str


class SynthesizedAnswer(BaseModel):
    """LLM synthesizes sub-answers (or a direct answer) into a final response."""

    answer: str
    key_points: list[str] = []


class ContradictionItem(BaseModel):
    """A single pair of contradicting claims found across documents."""

    claim_a: str
    claim_b: str
    document_a_title: str
    document_b_title: str
    severity: str   # "high" | "medium" | "low"


class ContradictionReport(BaseModel):
    """Full contradiction detection result across a set of documents."""

    contradictions: list[ContradictionItem]
    summary: str


class ComparisonReport(BaseModel):
    """Structured comparison result across two or more documents."""

    similarities: list[str]
    differences: list[str]
    summary: str
