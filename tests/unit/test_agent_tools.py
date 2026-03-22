"""
Unit tests for agents/tools.py.

RetrievalTool wraps query.services.execute_search — that call is mocked.
GenerationTool wraps StructuredLLMClient — uses an inline fake.
"""

import uuid
from unittest.mock import patch

import pytest

from agents.tools import GenerationTool, RetrievalTool
from analysis.exceptions import RetrievalAgentError, SynthesisError
from generation.llm import AnswerGenerationError
from retrieval.schemas import ChunkSearchResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(text: str = "excerpt text", page: int = 1) -> ChunkSearchResult:
    return ChunkSearchResult(
        chunk_id="c1",
        document_id=str(uuid.uuid4()),
        document_title="Test Doc",
        chunk_index=0,
        child_text=text,
        parent_text=text,
        page_number=page,
        score=0.9,
    )


class _FakeLLM:
    def __init__(
        self, *, should_fail: bool = False, answer: str = "fake answer"
    ) -> None:
        self.should_fail = should_fail
        self.answer = answer
        self.call_count = 0
        self.last_user_message: str = ""
        self.last_system_prompt: str = ""

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
        self.last_user_message = user_message
        self.last_system_prompt = system_prompt
        if self.should_fail:
            raise AnswerGenerationError("fake llm failure")
        return response_model()

    def generate_text(
        self, system_prompt, user_message, *, temperature, max_tokens, timeout
    ):
        self.call_count += 1
        self.last_user_message = user_message
        self.last_system_prompt = system_prompt
        if self.should_fail:
            raise AnswerGenerationError("fake llm failure")
        return self.answer


# ---------------------------------------------------------------------------
# RetrievalTool
# ---------------------------------------------------------------------------


class TestRetrievalTool:
    def test_retrieve_returns_chunk_search_results(self):
        chunks = [_make_chunk("relevant text")]
        with patch("agents.tools.execute_search", return_value=chunks, create=True):
            with patch("agents.tools.DocuMindError", create=True):
                # Patch the local imports inside retrieve()
                with patch("query.services.execute_search", return_value=chunks):
                    tool = RetrievalTool()
                    doc_id = uuid.uuid4()
                    result = tool.retrieve("What is the risk?", doc_id, k=5)
        assert result == chunks

    def test_retrieve_calls_execute_search_with_correct_args(self):
        doc_id = uuid.uuid4()
        with patch("query.services.execute_search", return_value=[]) as mock_search:
            tool = RetrievalTool()
            tool.retrieve("test query", doc_id, k=3)
        mock_search.assert_called_once_with(query="test query", document_id=doc_id, k=3)

    def test_retrieve_wraps_documind_error_as_retrieval_agent_error(self):
        from core.exceptions import DocuMindError

        with patch(
            "query.services.execute_search",
            side_effect=DocuMindError("retrieval broke"),
        ):
            tool = RetrievalTool()
            with pytest.raises(RetrievalAgentError):
                tool.retrieve("query", uuid.uuid4(), k=5)


# ---------------------------------------------------------------------------
# GenerationTool
# ---------------------------------------------------------------------------


class TestGenerationTool:
    def test_generate_answer_calls_structured_llm(self):
        llm = _FakeLLM(answer="the answer")
        tool = GenerationTool(structured_llm=llm)
        result = tool.generate_answer(
            question="What is the risk?",
            chunks=[_make_chunk()],
            prompt_key="sub_answer",
        )
        assert result == "the answer"
        assert llm.call_count == 1

    def test_generate_answer_includes_question_in_user_message(self):
        llm = _FakeLLM()
        tool = GenerationTool(structured_llm=llm)
        tool.generate_answer(
            question="What does section 3 say?",
            chunks=[_make_chunk()],
            prompt_key="sub_answer",
        )
        assert "What does section 3 say?" in llm.last_user_message

    def test_generate_answer_builds_context_block_from_chunks(self):
        llm = _FakeLLM()
        tool = GenerationTool(structured_llm=llm)
        chunk = _make_chunk("the key passage is here", page=5)
        tool.generate_answer(
            question="What?",
            chunks=[chunk],
            prompt_key="sub_answer",
        )
        assert "the key passage is here" in llm.last_user_message
        assert "Page 5" in llm.last_user_message

    def test_generate_answer_raises_synthesis_error_on_llm_failure(self):
        llm = _FakeLLM(should_fail=True)
        tool = GenerationTool(structured_llm=llm)
        with pytest.raises(SynthesisError):
            tool.generate_answer("What?", [_make_chunk()], prompt_key="sub_answer")

    def test_synthesize_formats_sub_questions_and_answers(self):
        llm = _FakeLLM(answer="synthesized")
        tool = GenerationTool(structured_llm=llm)
        result = tool.synthesize(
            original_question="Overall question",
            sub_questions=["Sub q 1", "Sub q 2"],
            sub_answers=["Answer 1", "Answer 2"],
        )
        assert result == "synthesized"
        assert "Sub-question 1: Sub q 1" in llm.last_user_message
        assert "Sub-question 2: Sub q 2" in llm.last_user_message
        assert "Answer 1" in llm.last_user_message
        assert "Overall question" in llm.last_user_message

    def test_synthesize_raises_synthesis_error_on_llm_failure(self):
        llm = _FakeLLM(should_fail=True)
        tool = GenerationTool(structured_llm=llm)
        with pytest.raises(SynthesisError):
            tool.synthesize("Q", ["sub q"], ["sub a"])
