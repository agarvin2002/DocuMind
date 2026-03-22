"""Evaluation report generation — JSON and Markdown output from an EvalResult.

Pure Python module: no Django imports, no RAGAS, no Redis.
Receives a fully-computed EvalResult and serialises it to disk.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from evaluation.constants import (
    ANSWER_RELEVANCY_THRESHOLD,
    BASELINE_IMPROVEMENT_MIN_PCT,
    CONTEXT_RECALL_THRESHOLD,
    FAITHFULNESS_THRESHOLD,
)

logger = logging.getLogger(__name__)


def generate_json_report(result: "EvalResult") -> str:  # noqa: F821
    """Return the full EvalResult as a formatted JSON string.

    Includes: run timestamp, verdict, dataset size, per-system scores,
    improvement percentages, and the thresholds the run was judged against.
    """
    payload = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "verdict": result.verdict,
        "dataset_size": result.dataset_size,
        "full_system": {
            "faithfulness": result.full_system.faithfulness,
            "answer_relevancy": result.full_system.answer_relevancy,
            "context_recall": result.full_system.context_recall,
            "sample_count": result.full_system.sample_count,
            "passed": result.full_system.passed,
        },
        "baseline": {
            "faithfulness": result.baseline.faithfulness,
            "answer_relevancy": result.baseline.answer_relevancy,
            "context_recall": result.baseline.context_recall,
            "sample_count": result.baseline.sample_count,
            "passed": result.baseline.passed,
        },
        "improvements_pct": result.improvements_pct,
        "thresholds": {
            "faithfulness_min": FAITHFULNESS_THRESHOLD,
            "answer_relevancy_min": ANSWER_RELEVANCY_THRESHOLD,
            "context_recall_min": CONTEXT_RECALL_THRESHOLD,
            "improvement_min_pct": BASELINE_IMPROVEMENT_MIN_PCT,
        },
    }
    return json.dumps(payload, indent=2)


def generate_markdown_report(result: "EvalResult") -> str:  # noqa: F821
    """Return a human-readable Markdown summary of the evaluation run."""
    fs = result.full_system
    bl = result.baseline
    imp = result.improvements_pct

    verdict_badge = "**PASS**" if result.verdict == "PASS" else "**FAIL**"
    run_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# DocuMind Evaluation Report",
        "",
        f"**Verdict:** {verdict_badge}  ",
        f"**Run at:** {run_at}  ",
        f"**Dataset size:** {result.dataset_size} samples",
        "",
        "## Metric Comparison",
        "",
        "| Metric | Full System | Baseline | Improvement | Threshold |",
        "|--------|-------------|----------|-------------|-----------|",
        f"| Faithfulness | {fs.faithfulness:.3f} | {bl.faithfulness:.3f} | {imp.get('faithfulness', 0.0):+.1f}% | ≥ {FAITHFULNESS_THRESHOLD:.2f} |",
        f"| Answer Relevancy | {fs.answer_relevancy:.3f} | {bl.answer_relevancy:.3f} | {imp.get('answer_relevancy', 0.0):+.1f}% | ≥ {ANSWER_RELEVANCY_THRESHOLD:.2f} |",
        f"| Context Recall | {fs.context_recall:.3f} | {bl.context_recall:.3f} | {imp.get('context_recall', 0.0):+.1f}% | ≥ {CONTEXT_RECALL_THRESHOLD:.2f} |",
        "",
        "## Verdict Details",
        "",
        f"- Full system passed absolute thresholds: {'Yes' if fs.passed else 'No'}",
        f"- Minimum improvement over baseline required: {BASELINE_IMPROVEMENT_MIN_PCT:.0f}%",
        f"- All improvements met minimum: {'Yes' if all(v >= BASELINE_IMPROVEMENT_MIN_PCT for v in imp.values()) else 'No'}",
    ]
    return "\n".join(lines)


def save_report(
    result: "EvalResult",  # noqa: F821
    output_dir: str = "eval_reports",
) -> tuple[Path, Path]:
    """Save JSON and Markdown reports to output_dir.

    Creates the directory if it does not exist.
    Returns (json_path, markdown_path).
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = out / f"eval_{timestamp}.json"
    md_path = out / f"eval_{timestamp}.md"

    json_path.write_text(generate_json_report(result), encoding="utf-8")
    md_path.write_text(generate_markdown_report(result), encoding="utf-8")

    logger.info(
        "Eval reports saved",
        extra={
            "json_path": str(json_path),
            "md_path": str(md_path),
            "verdict": result.verdict,
        },
    )
    return json_path, md_path
