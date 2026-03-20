"""Retrieval Precision@5 benchmark — hybrid vs. vector-only.

Measures what fraction of the top-5 retrieved chunks contain the ground-truth
answer text (substring match as a proxy for relevance).  No LLM calls, no RAGAS
— purely mechanical and fast.

Prerequisites:
    - Docker services running (postgres + redis)
    - Documents ingested: uv run python tests/evals/run_evals.py --dry-run
    - Eval documents generated: uv run python scripts/create_eval_docs.py

Usage:
    uv run python scripts/benchmark.py
    uv run python scripts/benchmark.py --k 5 --output-dir eval_reports
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django  # noqa: E402

django.setup()

from django.db import OperationalError, connection  # noqa: E402

from documents.models import Document  # noqa: E402
from documents.selectors import vector_search_chunks  # noqa: E402
from evaluation.constants import EVAL_DATASET_PATH  # noqa: E402
from evaluation.datasets import EvalDatasetLoader  # noqa: E402
from ingestion.embedders import SentenceTransformerEmbedder  # noqa: E402
from query.services import execute_search  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retrieval Precision@K benchmark")
    parser.add_argument("--k", type=int, default=5, help="Number of chunks to retrieve (default: 5)")
    parser.add_argument("--dataset-path", default=EVAL_DATASET_PATH)
    parser.add_argument("--output-dir", default="eval_reports")
    return parser.parse_args()


def _check_db() -> None:
    try:
        connection.ensure_connection()
    except OperationalError as exc:
        print(f"ERROR: Database unreachable — {exc}", file=sys.stderr)
        sys.exit(2)


def _resolve_doc_ids() -> dict[str, uuid.UUID]:
    """Return a mapping of document_title → UUID for ingested, ready documents."""
    docs = Document.objects.filter(status="ready")
    mapping: dict[str, uuid.UUID] = {}
    for d in docs:
        mapping[d.title] = d.id
    return mapping


def _is_relevant(chunk_text: str, ground_truth: str) -> bool:
    """Simple relevance proxy: ground truth keywords appear in chunk text."""
    gt_lower = ground_truth.lower()
    chunk_lower = chunk_text.lower()
    # Extract key terms (words > 5 chars) from ground truth and check presence
    key_terms = [w for w in gt_lower.split() if len(w) > 5]
    if not key_terms:
        return gt_lower[:30] in chunk_lower
    hits = sum(1 for t in key_terms if t in chunk_lower)
    return hits / len(key_terms) >= 0.4


def _precision_at_k(
    samples: list,
    doc_ids: dict[str, uuid.UUID],
    k: int,
    embedder: SentenceTransformerEmbedder,
) -> tuple[float, float, int]:
    """Compute Precision@K for hybrid and vector-only systems.

    Returns (hybrid_precision, vector_precision, evaluated_count).
    """
    hybrid_hits = 0
    vector_hits = 0
    evaluated = 0

    for sample in samples:
        doc_id = doc_ids.get(sample.document_title)
        if doc_id is None:
            continue

        evaluated += 1

        # Hybrid system (vector + BM25 + RRF + cross-encoder)
        try:
            hybrid_chunks = execute_search(sample.question, doc_id, k)
            hybrid_relevant = sum(
                1 for c in hybrid_chunks if _is_relevant(c.child_text, sample.ground_truth)
            )
            hybrid_hits += hybrid_relevant / k
        except Exception:  # noqa: BLE001
            pass

        # Vector-only baseline
        try:
            embedding = embedder.embed_single(sample.question)
            vector_chunks = vector_search_chunks(embedding, doc_id, k)
            vector_relevant = sum(
                1 for c in vector_chunks if _is_relevant(c.child_text, sample.ground_truth)
            )
            vector_hits += vector_relevant / k
        except Exception:  # noqa: BLE001
            pass

    if evaluated == 0:
        return 0.0, 0.0, 0

    return hybrid_hits / evaluated, vector_hits / evaluated, evaluated


def _save_results(hybrid: float, vector: float, k: int, evaluated: int, output_dir: str) -> Path:
    improvement_pct = ((hybrid - vector) / vector * 100) if vector > 0 else 0.0
    payload = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "k": k,
        "evaluated_samples": evaluated,
        f"precision_at_{k}": {
            "hybrid_system": round(hybrid, 4),
            "vector_only_baseline": round(vector, 4),
            "improvement_pct": round(improvement_pct, 2),
        },
    }
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out / f"benchmark_precision_at_{k}_{timestamp}.json"
    path.write_text(json.dumps(payload, indent=2))
    return path


def main() -> None:
    args = _parse_args()
    k = args.k

    print(f"DocuMind Retrieval Benchmark — Precision@{k}")
    print("-" * 50)

    _check_db()

    doc_ids = _resolve_doc_ids()
    if not doc_ids:
        print("ERROR: No ready documents found. Run: uv run python tests/evals/run_evals.py --dry-run", file=sys.stderr)
        sys.exit(2)

    print(f"Found {len(doc_ids)} ready document(s): {', '.join(doc_ids)}")

    samples = EvalDatasetLoader().load(path=args.dataset_path)
    # Only benchmark samples whose document is ingested
    samples = [s for s in samples if s.document_title in doc_ids]
    print(f"Benchmarking {len(samples)} samples...")

    embedder = SentenceTransformerEmbedder()
    hybrid_p, vector_p, evaluated = _precision_at_k(samples, doc_ids, k, embedder)

    improvement_pct = ((hybrid_p - vector_p) / vector_p * 100) if vector_p > 0 else 0.0

    print()
    print(f"  Precision@{k} Results ({evaluated} samples evaluated):")
    print(f"  {'Full system (hybrid+rerank)':<32}  {hybrid_p:.4f}")
    print(f"  {'Naive baseline (vector-only)':<32}  {vector_p:.4f}")
    print(f"  {'Improvement':<32}  {improvement_pct:+.1f}%")
    print()

    path = _save_results(hybrid_p, vector_p, k, evaluated, args.output_dir)
    print(f"Results saved to: {path}")

    sys.exit(0 if hybrid_p >= vector_p else 1)


if __name__ == "__main__":
    main()
