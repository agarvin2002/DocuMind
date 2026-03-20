"""Integration eval runner — runs the full RAGAS evaluation against a live DocuMind instance.

Prerequisites:
    - Docker services running (postgres, redis, celery worker)
    - OPENAI_API_KEY set (used by RAGAS judge LLM)
    - Eval documents generated: uv run python scripts/create_eval_docs.py

Usage:
    uv run python tests/evals/run_evals.py
    uv run python tests/evals/run_evals.py --dry-run       # 3 samples only
    uv run python tests/evals/run_evals.py --no-cache      # bypass Redis cache
    uv run python tests/evals/run_evals.py --dataset-path data/eval/qa_pairs.json

Exit codes:
    0 — PASS (all thresholds met, +20% over baseline on all metrics)
    1 — FAIL (any threshold missed or insufficient improvement)
    2 — Script error (DB unreachable, dataset not found, etc.)
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import uuid

# Django must be configured before any model imports.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django  # noqa: E402

django.setup()

import logging  # noqa: E402

from django.conf import settings as django_settings  # noqa: E402
from django.db import OperationalError, connection  # noqa: E402

from documents.models import Document  # noqa: E402
from documents.services import create_document, trigger_ingestion  # noqa: E402
from evaluation.adapters import FullSystemAdapter, NaiveBaselineAdapter  # noqa: E402
from evaluation.constants import (  # noqa: E402
    EVAL_DATASET_PATH,
    RAGAS_LLM_MODEL,
    RAGAS_OLLAMA_BASE_URL,
    RAGAS_OLLAMA_MODEL,
)
from evaluation.datasets import EvalDatasetLoader, EvalSample  # noqa: E402
from evaluation.harness import EvalHarness  # noqa: E402
from evaluation.metrics import RagasScorer  # noqa: E402
from evaluation.reports import save_report  # noqa: E402
from generation.structured import StructuredLLMClient  # noqa: E402
from ingestion.embedders import SentenceTransformerEmbedder  # noqa: E402

logger = logging.getLogger(__name__)

# Titles in qa_pairs.json → actual PDF file paths
_DOCUMENT_TITLE_TO_PDF = {
    "ai_concepts": "data/eval/documents/ai_concepts.pdf",
    "product_spec": "data/eval/documents/product_spec.pdf",
    "science_report": "data/eval/documents/science_report.pdf",
}

# Time to wait per-poll when waiting for document ingestion to complete
_INGESTION_POLL_INTERVAL_SEC = 3
_INGESTION_TIMEOUT_SEC = 300


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DocuMind RAGAS evaluation runner")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run with only the first 3 samples (fast smoke test, no LLM calls counted)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Bypass Redis cache and force a fresh evaluation run",
    )
    parser.add_argument(
        "--dataset-path",
        default=EVAL_DATASET_PATH,
        help=f"Path to qa_pairs.json (default: {EVAL_DATASET_PATH})",
    )
    parser.add_argument(
        "--output-dir",
        default="eval_reports",
        help="Directory to save JSON and Markdown reports (default: eval_reports)",
    )
    return parser.parse_args()


def _check_db() -> None:
    """Fail fast with a clear error if the database is not reachable."""
    try:
        connection.ensure_connection()
    except OperationalError as exc:
        print(f"ERROR: Database is not reachable — {exc}", file=sys.stderr)
        print("Ensure Docker services are running: docker compose up -d", file=sys.stderr)
        sys.exit(2)


def _get_or_ingest_document(title: str) -> uuid.UUID:
    """Return the UUID of the ingested document with the given title.

    Ingests the document if it does not already exist in the database.
    Raises SystemExit(2) if the PDF file is missing or ingestion fails.
    """
    existing = Document.objects.filter(title=title).order_by("-created_at").first()
    if existing and existing.status == "ready":
        logger.info("Document already ingested", extra={"title": title, "document_id": str(existing.id)})
        return existing.id

    pdf_path = _DOCUMENT_TITLE_TO_PDF.get(title)
    if not pdf_path or not os.path.exists(pdf_path):
        print(
            f"ERROR: PDF for '{title}' not found at '{pdf_path}'. "
            f"Run: uv run python scripts/create_eval_docs.py",
            file=sys.stderr,
        )
        sys.exit(2)

    print(f"  Ingesting '{title}' from {pdf_path}...")
    with open(pdf_path, "rb") as fh:
        pdf_bytes = fh.read()

    document = create_document(
        title=title,
        file_content=pdf_bytes,
        file_name=os.path.basename(pdf_path),
        file_size=len(pdf_bytes),
        mime_type="application/pdf",
    )
    trigger_ingestion(document.id)

    # Wait for Celery worker to process the document
    deadline = time.monotonic() + _INGESTION_TIMEOUT_SEC
    while time.monotonic() < deadline:
        document.refresh_from_db()
        if document.status == "ready":
            print(f"  '{title}' ready (id={document.id})")
            return document.id
        if document.status == "failed":
            print(f"ERROR: Ingestion failed for '{title}'", file=sys.stderr)
            sys.exit(2)
        time.sleep(_INGESTION_POLL_INTERVAL_SEC)

    print(f"ERROR: Ingestion timed out after {_INGESTION_TIMEOUT_SEC}s for '{title}'", file=sys.stderr)
    sys.exit(2)


def _resolve_document_ids(samples: list[EvalSample]) -> list[EvalSample]:
    """Replace the empty document_id in each sample with the real UUID.

    Groups samples by document_title, ingests each document once,
    then returns a new list of EvalSample instances with document_id populated.
    """
    titles = {s.document_title for s in samples}
    title_to_uuid: dict[str, str] = {}

    for title in sorted(titles):
        doc_id = _get_or_ingest_document(title)
        title_to_uuid[title] = str(doc_id)

    resolved = []
    for s in samples:
        resolved.append(
            EvalSample(
                question=s.question,
                ground_truth=s.ground_truth,
                document_id=title_to_uuid[s.document_title],
                document_title=s.document_title,
                tags=s.tags,
            )
        )
    return resolved


def _print_summary(result: "EvalResult") -> None:  # noqa: F821
    fs = result.full_system
    bl = result.baseline
    imp = result.improvements_pct

    print()
    print("=" * 60)
    print(f"  Verdict: {result.verdict}   (dataset: {result.dataset_size} samples)")
    print("=" * 60)
    print(f"  {'Metric':<22} {'Full System':>12} {'Baseline':>10} {'Improvement':>12}")
    print(f"  {'-'*22} {'-'*12} {'-'*10} {'-'*12}")
    print(f"  {'Faithfulness':<22} {fs.faithfulness:>12.3f} {bl.faithfulness:>10.3f} {imp.get('faithfulness', 0.0):>+11.1f}%")
    print(f"  {'Answer Relevancy':<22} {fs.answer_relevancy:>12.3f} {bl.answer_relevancy:>10.3f} {imp.get('answer_relevancy', 0.0):>+11.1f}%")
    print(f"  {'Context Recall':<22} {fs.context_recall:>12.3f} {bl.context_recall:>10.3f} {imp.get('context_recall', 0.0):>+11.1f}%")
    print("=" * 60)
    print()


def main() -> None:
    args = _parse_args()

    logging.basicConfig(level=logging.WARNING)
    logger.setLevel(logging.INFO)

    print("DocuMind Evaluation Runner")
    print("-" * 40)

    _check_db()

    # Load dataset
    loader = EvalDatasetLoader()
    all_samples = loader.load(path=args.dataset_path)
    samples = all_samples[:3] if args.dry_run else all_samples
    print(f"Loaded {len(samples)} samples{'  [DRY RUN]' if args.dry_run else ''}")

    # Ingest documents and resolve UUIDs
    print("Resolving document IDs...")
    samples = _resolve_document_ids(samples)

    # Build components
    llm = StructuredLLMClient()
    embedder = SentenceTransformerEmbedder()
    full_system = FullSystemAdapter(llm=llm)
    baseline = NaiveBaselineAdapter(llm=llm, embedder=embedder)
    scorer = RagasScorer(
        provider=getattr(django_settings, "RAGAS_JUDGE_PROVIDER", "openai"),
        openai_model=getattr(django_settings, "RAGAS_LLM_MODEL", RAGAS_LLM_MODEL),
        ollama_model=getattr(django_settings, "RAGAS_OLLAMA_MODEL", RAGAS_OLLAMA_MODEL),
        ollama_base_url=getattr(django_settings, "OLLAMA_BASE_URL", RAGAS_OLLAMA_BASE_URL),
    )

    # Build harness (no Redis pool in this runner — keep it dependency-light)
    harness = EvalHarness(
        full_system=full_system,
        baseline=baseline,
        scorer=scorer,
        redis_pool=None,
    )

    print("Running evaluation (this may take several minutes)...")
    result = harness.run(samples, use_cache=not args.no_cache)

    # Print and save
    _print_summary(result)
    json_path, md_path = save_report(result, output_dir=args.output_dir)
    print("Reports saved:")
    print(f"  JSON: {json_path}")
    print(f"  Markdown: {md_path}")
    print()

    sys.exit(0 if result.verdict == "PASS" else 1)


if __name__ == "__main__":
    main()
