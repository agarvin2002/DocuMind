"""RAGAS metric computation and threshold checking for RAG evaluation."""

import concurrent.futures
import logging
from dataclasses import dataclass

from evaluation.constants import (
    ANSWER_RELEVANCY_THRESHOLD,
    CONTEXT_RECALL_THRESHOLD,
    EVAL_RAGAS_TIMEOUT_SECONDS,
    FAITHFULNESS_THRESHOLD,
    RAGAS_JUDGE_MAX_TOKENS,
    RAGAS_JUDGE_TEMPERATURE,
    RAGAS_LLM_MODEL,
    RAGAS_OLLAMA_BASE_URL,
    RAGAS_OLLAMA_MODEL,
)
from evaluation.exceptions import MetricComputeError
from evaluation.protocols import RAGScorerPort

logger = logging.getLogger(__name__)

# Keys RAGAS returns — used to extract scores from the result dict safely.
_FAITHFULNESS_KEY = "faithfulness"
_ANSWER_RELEVANCY_KEY = "answer_relevancy"
_CONTEXT_RECALL_KEY = "context_recall"


# Plain dataclass (not Pydantic) — internal eval container; no HTTP boundary validation needed.
@dataclass
class MetricResult:
    """Scores and pass/fail verdict for a single eval run."""

    faithfulness: float
    answer_relevancy: float
    context_recall: float
    sample_count: int
    passed: bool


def passes_thresholds(faithfulness: float, answer_relevancy: float, context_recall: float) -> bool:
    """Return True only if all three scores clear the thresholds in constants.py."""
    return (
        faithfulness >= FAITHFULNESS_THRESHOLD
        and answer_relevancy >= ANSWER_RELEVANCY_THRESHOLD
        and context_recall >= CONTEXT_RECALL_THRESHOLD
    )


def compute_ragas_metrics(
    questions: list[str],
    answers: list[str],
    contexts: list[list[str]],
    ground_truths: list[str],
    *,
    scorer: RAGScorerPort,
) -> MetricResult:
    """Score a batch of RAG outputs and return a typed MetricResult.

    Delegates the actual scoring to the injected scorer — never calls RAGAS directly.
    This keeps the harness free of RAGAS imports and trivially testable with FakeRAGScorer.

    Raises:
        MetricComputeError: If the scorer raises any exception.
    """
    n = len(questions)
    logger.info("Starting metric computation", extra={"sample_count": n})

    try:
        scores = scorer.score(questions, answers, contexts, ground_truths)
    except MetricComputeError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise MetricComputeError(
            f"Scorer raised an unexpected error: {exc}"
        ) from exc

    faithfulness = float(scores.get(_FAITHFULNESS_KEY, 0.0))
    answer_relevancy = float(scores.get(_ANSWER_RELEVANCY_KEY, 0.0))
    context_recall = float(scores.get(_CONTEXT_RECALL_KEY, 0.0))
    passed = passes_thresholds(faithfulness, answer_relevancy, context_recall)

    logger.info(
        "Metric computation complete",
        extra={
            "faithfulness": faithfulness,
            "answer_relevancy": answer_relevancy,
            "context_recall": context_recall,
            "passed": passed,
        },
    )

    return MetricResult(
        faithfulness=faithfulness,
        answer_relevancy=answer_relevancy,
        context_recall=context_recall,
        sample_count=n,
        passed=passed,
    )


class RagasScorer:
    """Production scorer — calls real RAGAS evaluate() with a configurable judge LLM.

    Satisfies RAGScorerPort. Imports RAGAS lazily to keep module load fast.
    Configuration is injected at construction time so this class stays pure Python
    with zero Django imports.
    """

    def __init__(
        self,
        *,
        provider: str = "openai",
        openai_model: str = RAGAS_LLM_MODEL,
        ollama_model: str = RAGAS_OLLAMA_MODEL,
        ollama_base_url: str = RAGAS_OLLAMA_BASE_URL,
    ) -> None:
        self._provider = provider
        self._openai_model = openai_model
        self._ollama_model = ollama_model
        self._ollama_base_url = ollama_base_url

        logger.info(
            "RagasScorer initialised",
            extra={"provider": self._provider, "model": self._ollama_model if self._provider == "ollama" else self._openai_model},
        )

    def _build_judge_llm(self):
        """Build the LangChain-wrapped judge LLM for the configured provider."""
        from langchain_openai import ChatOpenAI
        from ragas.llms import LangchainLLMWrapper

        if self._provider == "ollama":
            # Ollama exposes an OpenAI-compatible API at /v1 — same trick as OllamaProvider.
            # A dummy API key is required by the SDK but is not validated by Ollama.
            chat = ChatOpenAI(
                model=self._ollama_model,
                base_url=self._ollama_base_url,
                api_key="ollama",  # noqa: S106 — dummy key, Ollama does not validate it
                temperature=RAGAS_JUDGE_TEMPERATURE,
                max_tokens=RAGAS_JUDGE_MAX_TOKENS,
            )
        else:
            chat = ChatOpenAI(
                model=self._openai_model,
                temperature=RAGAS_JUDGE_TEMPERATURE,
                max_tokens=RAGAS_JUDGE_MAX_TOKENS,
            )

        return LangchainLLMWrapper(chat)

    def score(
        self,
        questions: list[str],
        answers: list[str],
        contexts: list[list[str]],
        ground_truths: list[str],
    ) -> dict[str, float]:
        """Build a RAGAS EvaluationDataset and run faithfulness, answer relevancy, and context recall.

        Raises:
            MetricComputeError: If RAGAS or the judge LLM raises any exception.
        """
        try:
            from ragas import EvaluationDataset, SingleTurnSample, evaluate
            from ragas.metrics import AnswerRelevancy, ContextRecall, Faithfulness
        except ImportError as exc:
            raise MetricComputeError(
                "RAGAS dependencies are not installed. Run: uv add ragas datasets"
            ) from exc

        try:
            judge_llm = self._build_judge_llm()

            samples = [
                SingleTurnSample(
                    user_input=q,
                    response=a,
                    retrieved_contexts=ctx,
                    reference=gt,
                )
                for q, a, ctx, gt in zip(questions, answers, contexts, ground_truths)
            ]
            dataset = EvaluationDataset(samples=samples)

            metrics = [
                Faithfulness(llm=judge_llm),
                AnswerRelevancy(llm=judge_llm),
                ContextRecall(llm=judge_llm),
            ]

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(evaluate, dataset, metrics=metrics)
                try:
                    result = future.result(timeout=EVAL_RAGAS_TIMEOUT_SECONDS)
                except concurrent.futures.TimeoutError as exc:
                    raise MetricComputeError(
                        f"RAGAS evaluation timed out after {EVAL_RAGAS_TIMEOUT_SECONDS}s"
                    ) from exc

            scores = result.to_pandas().mean(numeric_only=True).to_dict()

            return {
                _FAITHFULNESS_KEY: float(scores.get("faithfulness", 0.0)),
                _ANSWER_RELEVANCY_KEY: float(scores.get("answer_relevancy", 0.0)),
                _CONTEXT_RECALL_KEY: float(scores.get("context_recall", 0.0)),
            }

        except MetricComputeError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise MetricComputeError(
                f"RAGAS evaluation failed: {exc}"
            ) from exc
