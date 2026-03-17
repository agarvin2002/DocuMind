"""
agents/tools.py — Adapter classes that connect graph nodes to the retrieval
and generation layers.

Graph nodes never import from query/ or generation/ directly. They go through
these adapters, which:
  - Translate between layers (e.g. DocuMindError → RetrievalAgentError)
  - Own all prompt selection and context formatting logic
  - Can be swapped for fakes in tests without touching node code

Usage:
    retrieval_tool = RetrievalTool()
    gen_tool = GenerationTool(structured_llm=StructuredLLMClient(...))
"""

import logging
import uuid

from agents.constants import (
    AGENT_GENERATION_TEMPERATURE,
    AGENT_LLM_TIMEOUT,
    AGENT_SUBQUERY_MAX_TOKENS,
    AGENT_SYNTHESIS_MAX_TOKENS,
)
from agents.protocols import StructuredLLMPort
from agents.schemas import SynthesizedAnswer
from analysis.exceptions import RetrievalAgentError, SynthesisError
from generation.prompts import build_context_block, get_agent_prompt
from retrieval.schemas import ChunkSearchResult

logger = logging.getLogger(__name__)


class RetrievalTool:
    """
    Adapter wrapping query.services.execute_search for use inside graph nodes.

    Satisfies agents/protocols.RetrievalToolPort.

    Local import of execute_search avoids a circular import at module load time:
    agents/ → query/ → agents/ (if agents/ were imported at query/'s top level).
    """

    def retrieve(
        self,
        query: str,
        document_id: uuid.UUID,
        k: int,
    ) -> list[ChunkSearchResult]:
        """
        Run the full hybrid retrieval pipeline for a single document.

        Args:
            query:       The search query (sub-question or original question).
            document_id: UUID of the document to search within.
            k:           Number of chunks to return.

        Returns:
            List of ChunkSearchResult, ranked by relevance.

        Raises:
            RetrievalAgentError: wrapping any DocuMindError from the retrieval pipeline.
        """
        from core.exceptions import DocuMindError
        from query.services import execute_search

        logger.debug(
            "agent_retrieval_start",
            extra={"document_id": str(document_id), "k": k},
        )
        try:
            results = execute_search(query=query, document_id=document_id, k=k)
        except DocuMindError as exc:
            raise RetrievalAgentError(
                f"Retrieval failed for document {document_id}: {exc}"
            ) from exc

        logger.debug(
            "agent_retrieval_complete",
            extra={"document_id": str(document_id), "result_count": len(results)},
        )
        return results


class GenerationTool:
    """
    Adapter wrapping StructuredLLMClient for non-streaming answer generation
    inside graph nodes.

    Satisfies agents/protocols usage inside graph nodes.
    """

    def __init__(self, structured_llm: StructuredLLMPort) -> None:
        self._llm = structured_llm

    def generate_answer(
        self,
        question: str,
        chunks: list[ChunkSearchResult],
        prompt_key: str,
    ) -> str:
        """
        Generate an answer to question using the retrieved chunks as context.

        Used for: sub-question answers (multi-hop), simple pass-through, comparison.

        Args:
            question:   The (sub-)question to answer.
            chunks:     Retrieved chunks forming the context window.
            prompt_key: Key into AGENT_PROMPTS (e.g. "sub_answer", "comparison").

        Returns:
            Plain string answer.

        Raises:
            SynthesisError: if the LLM call fails.
        """
        context_block = build_context_block(chunks)
        system_prompt = get_agent_prompt(prompt_key)
        user_message = f"Context:\n{context_block}\n\nQuestion: {question}"

        try:
            result: SynthesizedAnswer = self._llm.complete(
                system_prompt=system_prompt,
                user_message=user_message,
                response_model=SynthesizedAnswer,
                temperature=AGENT_GENERATION_TEMPERATURE,
                max_tokens=AGENT_SUBQUERY_MAX_TOKENS,
                timeout=AGENT_LLM_TIMEOUT,
            )
            return result.answer
        except Exception as exc:
            raise SynthesisError(f"Answer generation failed: {exc}") from exc

    def synthesize(
        self,
        original_question: str,
        sub_questions: list[str],
        sub_answers: list[str],
    ) -> str:
        """
        Combine multiple sub-answers into a single unified response.

        Used for: the final synthesis step in multi-hop workflows.

        Args:
            original_question: The user's original question.
            sub_questions:     The decomposed sub-questions (same order as sub_answers).
            sub_answers:       One answer per sub-question.

        Returns:
            Plain string synthesized answer.

        Raises:
            SynthesisError: if the LLM call fails.
        """
        sub_qa_block = "\n\n".join(
            f"Sub-question {i + 1}: {q}\nAnswer: {a}"
            for i, (q, a) in enumerate(zip(sub_questions, sub_answers))
        )
        user_message = f"Original question: {original_question}\n\n{sub_qa_block}"

        try:
            result: SynthesizedAnswer = self._llm.complete(
                system_prompt=get_agent_prompt("synthesis"),
                user_message=user_message,
                response_model=SynthesizedAnswer,
                temperature=AGENT_GENERATION_TEMPERATURE,
                max_tokens=AGENT_SYNTHESIS_MAX_TOKENS,
                timeout=AGENT_LLM_TIMEOUT,
            )
            return result.answer
        except Exception as exc:
            raise SynthesisError(f"Synthesis failed: {exc}") from exc
