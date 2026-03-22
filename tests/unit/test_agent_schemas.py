"""
Unit tests for agents/schemas.py.

Pydantic models are validated on instantiation — tests confirm fields are present,
types are enforced, and defaults work as expected.
"""

import pytest

from agents.schemas import (
    ComparisonReport,
    ComplexityClassification,
    ContradictionItem,
    ContradictionReport,
    QueryDecomposition,
    SubQueryResult,
    SynthesizedAnswer,
)


class TestAgentSchemas:
    def test_complexity_classification_validates_fields(self):
        obj = ComplexityClassification(
            complexity="complex",
            workflow_type="multi_hop",
            reasoning="requires multiple retrieval steps",
        )
        assert obj.complexity == "complex"
        assert obj.workflow_type == "multi_hop"
        assert obj.reasoning

    def test_query_decomposition_requires_sub_questions(self):
        obj = QueryDecomposition(
            sub_questions=["What is A?", "How does A relate to B?"],
            reasoning="two-step reasoning needed",
        )
        assert len(obj.sub_questions) == 2

    def test_query_decomposition_rejects_missing_sub_questions(self):
        with pytest.raises(Exception):
            QueryDecomposition(reasoning="no sub questions provided")

    def test_contradiction_item_severity_field_present(self):
        item = ContradictionItem(
            claim_a="X is true",
            claim_b="X is false",
            document_a_title="Doc A",
            document_b_title="Doc B",
            severity="high",
        )
        assert item.severity == "high"

    def test_sub_query_result_defaults(self):
        result = SubQueryResult(sub_question="What?", document_id="doc-123")
        assert result.chunks == []
        assert result.answer == ""

    def test_sub_query_result_stores_answer(self):
        result = SubQueryResult(
            sub_question="What?",
            document_id="doc-123",
            answer="The answer is 42.",
        )
        assert result.answer == "The answer is 42."

    def test_synthesized_answer_has_key_points(self):
        obj = SynthesizedAnswer(
            answer="Final answer.", key_points=["Point 1", "Point 2"]
        )
        assert len(obj.key_points) == 2

    def test_comparison_report_has_similarities_and_differences(self):
        obj = ComparisonReport(
            similarities=["Both discuss risk"],
            differences=["Doc A focuses on market risk, Doc B on credit risk"],
            summary="The documents are broadly similar but differ in scope.",
        )
        assert obj.similarities
        assert obj.differences

    def test_contradiction_report_with_no_contradictions(self):
        obj = ContradictionReport(contradictions=[], summary="No contradictions found.")
        assert obj.contradictions == []
        assert "No contradictions" in obj.summary
