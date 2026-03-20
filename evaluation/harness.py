"""Evaluation harness — orchestrates dataset loading, answer collection, scoring, and caching."""

import hashlib
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from uuid import UUID

import redis as redis_lib

from evaluation.constants import (
    BASELINE_IMPROVEMENT_MIN_PCT,
    EVAL_BASELINE_K,
    EVAL_CACHE_PREFIX,
    EVAL_CACHE_TTL,
    EVAL_MAX_WORKERS,
    EVAL_SYSTEM_K,
)
from evaluation.datasets import EvalSample
from evaluation.exceptions import EvaluationError
from evaluation.metrics import MetricResult, compute_ragas_metrics
from evaluation.protocols import RAGScorerPort, RAGSystemPort

logger = logging.getLogger(__name__)


# Plain dataclass (not Pydantic) — internal eval container; no HTTP boundary validation needed.
@dataclass
class EvalResult:
    """Full comparison between the full system and the naive baseline."""

    full_system: MetricResult
    baseline: MetricResult
    improvements_pct: dict[str, float]
    verdict: str  # "PASS" or "FAIL"
    dataset_size: int


class EvalHarness:
    """Orchestrates a full evaluation run with Redis caching.

    Caches by hash of (question texts + system config) so re-runs on the same
    dataset are free. Redis failures are non-fatal — eval proceeds without cache.
    """

    def __init__(
        self,
        full_system: RAGSystemPort,
        baseline: RAGSystemPort,
        scorer: RAGScorerPort,
        redis_pool: redis_lib.ConnectionPool | None = None,
    ) -> None:
        self._full_system = full_system
        self._baseline = baseline
        self._scorer = scorer
        self._redis_pool = redis_pool

    def run(
        self,
        samples: list[EvalSample],
        *,
        use_cache: bool = True,
    ) -> EvalResult:
        """Run the full evaluation: collect answers for both systems, score, compare, cache.

        Raises:
            EvaluationError: If answer collection or scoring fails unrecoverably.
        """
        cache_key = self._compute_cache_key(samples)

        if use_cache:
            cached = self._read_cache(cache_key)
            if cached is not None:
                logger.info("Eval result served from cache", extra={"cache_key": cache_key})
                return cached

        logger.info("Starting eval run", extra={"sample_count": len(samples)})

        full_rows = self._collect_answers(samples, self._full_system, EVAL_SYSTEM_K)
        baseline_rows = self._collect_answers(samples, self._baseline, EVAL_BASELINE_K)

        full_result = compute_ragas_metrics(
            questions=[r[0].question for r in full_rows],
            answers=[r[1] for r in full_rows],
            contexts=[r[2] for r in full_rows],
            ground_truths=[r[0].ground_truth for r in full_rows],
            scorer=self._scorer,
        )
        baseline_result = compute_ragas_metrics(
            questions=[r[0].question for r in baseline_rows],
            answers=[r[1] for r in baseline_rows],
            contexts=[r[2] for r in baseline_rows],
            ground_truths=[r[0].ground_truth for r in baseline_rows],
            scorer=self._scorer,
        )

        improvements_pct = _compute_improvements(full_result, baseline_result)
        verdict = _determine_verdict(full_result, improvements_pct)

        result = EvalResult(
            full_system=full_result,
            baseline=baseline_result,
            improvements_pct=improvements_pct,
            verdict=verdict,
            dataset_size=len(samples),
        )

        if use_cache:
            self._write_cache(cache_key, result)

        logger.info("Eval run complete", extra={"verdict": verdict})
        return result

    def _collect_answers(
        self,
        samples: list[EvalSample],
        rag_system: RAGSystemPort,
        k: int,
    ) -> list[tuple[EvalSample, str, list[str]]]:
        """Run all samples through rag_system concurrently.

        Samples that raise an exception are skipped with a warning rather than
        crashing the entire run — consistent with the non-fatal Redis pattern.
        """
        results: list[tuple[EvalSample, str, list[str]]] = []

        with ThreadPoolExecutor(max_workers=EVAL_MAX_WORKERS) as executor:
            def _resolve_uuid(s: EvalSample) -> UUID:
                if not s.document_id:
                    logger.warning(
                        "Sample has empty document_id — using null UUID; will likely find no chunks",
                        extra={"question": s.question[:80]},
                    )
                    return UUID(int=0)
                return UUID(s.document_id)

            futures = {
                executor.submit(rag_system.answer, s.question, _resolve_uuid(s), k): s
                for s in samples
            }
            for future in as_completed(futures):
                sample = futures[future]
                try:
                    answer, contexts = future.result()
                    results.append((sample, answer, contexts))
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Sample skipped due to error during answer collection",
                        extra={
                            "question": sample.question[:80],
                            "error_type": type(exc).__name__,
                        },
                    )

        if not results:
            raise EvaluationError("All samples failed during answer collection.")

        return results

    def _compute_cache_key(self, samples: list[EvalSample]) -> str:
        config = {
            "system_k": EVAL_SYSTEM_K,
            "baseline_k": EVAL_BASELINE_K,
        }
        payload = {
            "questions": sorted(s.question for s in samples),
            "config": config,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()[:32]
        return f"{EVAL_CACHE_PREFIX}{digest}"

    def _read_cache(self, key: str) -> EvalResult | None:
        if self._redis_pool is None:
            return None
        try:
            conn = redis_lib.Redis(connection_pool=self._redis_pool)
            raw = conn.get(key)
            if raw is None:
                return None
            return _deserialize_result(json.loads(raw))
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Eval cache read failed — proceeding without cache",
                extra={"key": key, "error_type": type(exc).__name__},
            )
            return None

    def _write_cache(self, key: str, result: EvalResult) -> None:
        if self._redis_pool is None:
            return
        try:
            conn = redis_lib.Redis(connection_pool=self._redis_pool)
            conn.set(key, json.dumps(_serialize_result(result)), ex=EVAL_CACHE_TTL)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Eval cache write failed — result not cached",
                extra={"key": key, "error_type": type(exc).__name__},
            )


# --- helpers ---

def _compute_improvements(full: MetricResult, baseline: MetricResult) -> dict[str, float]:
    """Calculate percentage improvement of full system over baseline for each metric.

    Returns 0.0 for any metric where the baseline score is zero to avoid division by zero.
    """
    def _pct(full_score: float, base_score: float) -> float:
        if base_score == 0.0:
            return 0.0
        return round(((full_score - base_score) / base_score) * 100, 2)

    return {
        "faithfulness": _pct(full.faithfulness, baseline.faithfulness),
        "answer_relevancy": _pct(full.answer_relevancy, baseline.answer_relevancy),
        "context_recall": _pct(full.context_recall, baseline.context_recall),
    }


def _determine_verdict(full: MetricResult, improvements_pct: dict[str, float]) -> str:
    """PASS requires: full system clears all absolute thresholds AND beats baseline by ≥20% on all metrics."""
    if not full.passed:
        return "FAIL"
    if any(v < BASELINE_IMPROVEMENT_MIN_PCT for v in improvements_pct.values()):
        return "FAIL"
    return "PASS"


def _serialize_result(result: EvalResult) -> dict:
    def _metric(m: MetricResult) -> dict:
        return {
            "faithfulness": m.faithfulness,
            "answer_relevancy": m.answer_relevancy,
            "context_recall": m.context_recall,
            "sample_count": m.sample_count,
            "passed": m.passed,
        }

    return {
        "full_system": _metric(result.full_system),
        "baseline": _metric(result.baseline),
        "improvements_pct": result.improvements_pct,
        "verdict": result.verdict,
        "dataset_size": result.dataset_size,
    }


def _deserialize_result(data: dict) -> EvalResult:
    def _metric(d: dict) -> MetricResult:
        return MetricResult(
            faithfulness=d["faithfulness"],
            answer_relevancy=d["answer_relevancy"],
            context_recall=d["context_recall"],
            sample_count=d["sample_count"],
            passed=d["passed"],
        )

    return EvalResult(
        full_system=_metric(data["full_system"]),
        baseline=_metric(data["baseline"]),
        improvements_pct=data["improvements_pct"],
        verdict=data["verdict"],
        dataset_size=data["dataset_size"],
    )
