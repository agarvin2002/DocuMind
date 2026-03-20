from typing import Protocol, runtime_checkable
from uuid import UUID


@runtime_checkable
class RAGSystemPort(Protocol):
    """Any RAG system under evaluation must implement this interface.

    Returns both the generated answer and the retrieved context passages so
    RAGAS can score faithfulness (grounding) and context recall (retrieval quality).
    """

    def answer(
        self,
        question: str,
        document_id: UUID,
        k: int,
    ) -> tuple[str, list[str]]:
        """Run the full retrieve-then-generate pipeline for one question.

        Returns:
            A tuple of (answer_text, retrieved_contexts) where retrieved_contexts
            is the list of raw chunk texts the system retrieved before generating.
        """
        ...


@runtime_checkable
class RAGScorerPort(Protocol):
    """Abstracts the RAGAS evaluate() call behind a testable interface.

    Keeping the harness free of direct RAGAS imports means the scorer can be
    swapped for a fake in unit tests without touching any RAGAS internals.
    """

    def score(
        self,
        questions: list[str],
        answers: list[str],
        contexts: list[list[str]],
        ground_truths: list[str],
    ) -> dict[str, float]:
        """Score a batch of RAG outputs.

        Returns:
            Mapping of metric name to score averaged across all samples,
            e.g. {"faithfulness": 0.87, "answer_relevancy": 0.82, "context_recall": 0.79}.
        """
        ...
