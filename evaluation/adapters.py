"""Adapters that bridge evaluation/protocols.RAGSystemPort to the real DocuMind pipeline.

This is the only file in evaluation/ that imports from Django app modules.
All other evaluation files are pure Python — this file is the controlled boundary layer.
Django app imports are deferred inside method bodies to avoid triggering the app registry
at module load time, matching the pattern used in analysis/services.py.
"""

import logging
from uuid import UUID

from agents.protocols import StructuredLLMPort
from evaluation.constants import (
    EVAL_GENERATION_MAX_TOKENS,
    EVAL_GENERATION_TEMPERATURE,
    EVAL_GENERATION_TIMEOUT_SECONDS,
)
from evaluation.exceptions import BaselineError
from ingestion.protocols import EmbedderProtocol

logger = logging.getLogger(__name__)


class FullSystemAdapter:
    """Wraps DocuMind's full hybrid retrieval + generation pipeline as a RAGSystemPort.

    Calls execute_search() (vector + BM25 + RRF + cross-encoder reranking) then
    generates an answer with the injected LLM. Returns both the answer and the raw
    retrieved chunk texts so RAGAS can score faithfulness and context recall.
    """

    def __init__(self, llm: StructuredLLMPort) -> None:
        self._llm = llm

    def answer(self, question: str, document_id: UUID, k: int) -> tuple[str, list[str]]:
        """Run full hybrid retrieval then generate an answer.

        Raises:
            EvaluationError: If retrieval or generation fails.
        """
        from generation.prompts import build_user_message, get_system_prompt
        from query.services import execute_search

        chunks = execute_search(question, document_id, k)
        contexts = [c.child_text for c in chunks]

        logger.debug(
            "FullSystemAdapter retrieved chunks",
            extra={"question": question[:80], "chunk_count": len(chunks)},
        )

        answer_text = self._llm.generate_text(
            system_prompt=get_system_prompt(),
            user_message=build_user_message(question, chunks, max_context_tokens=6000),
            temperature=EVAL_GENERATION_TEMPERATURE,
            max_tokens=EVAL_GENERATION_MAX_TOKENS,
            timeout=EVAL_GENERATION_TIMEOUT_SECONDS,
        )

        return answer_text, contexts


class NaiveBaselineAdapter:
    """Wraps a vector-only RAG pipeline as a RAGSystemPort.

    Bypasses BM25, RRF fusion, and cross-encoder reranking — calls
    vector_search_chunks() directly. Uses the same LLM and prompt as
    FullSystemAdapter so the comparison measures retrieval quality alone.
    """

    def __init__(self, llm: StructuredLLMPort, embedder: EmbedderProtocol) -> None:
        self._llm = llm
        self._embedder = embedder

    def answer(self, question: str, document_id: UUID, k: int) -> tuple[str, list[str]]:
        """Run vector-only retrieval then generate an answer.

        Raises:
            BaselineError: If retrieval or generation fails.
        """
        try:
            from documents.selectors import vector_search_chunks
            from generation.prompts import build_user_message, get_system_prompt

            embedding = self._embedder.embed_single(question)
            chunks = vector_search_chunks(embedding, document_id, k)
            contexts = [c.child_text for c in chunks]

            logger.debug(
                "NaiveBaselineAdapter retrieved chunks",
                extra={"question": question[:80], "chunk_count": len(chunks)},
            )

            answer_text = self._llm.generate_text(
                system_prompt=get_system_prompt(),
                user_message=build_user_message(
                    question, chunks, max_context_tokens=6000
                ),
                temperature=EVAL_GENERATION_TEMPERATURE,
                max_tokens=EVAL_GENERATION_MAX_TOKENS,
                timeout=EVAL_GENERATION_TIMEOUT_SECONDS,
            )

            return answer_text, contexts

        except BaselineError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise BaselineError(
                f"Naive baseline failed for question '{question[:60]}': {exc}"
            ) from exc
