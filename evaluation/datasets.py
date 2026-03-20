"""Evaluation dataset loading and validation.

Usage:
    loader = EvalDatasetLoader()
    samples = loader.load("data/eval/qa_pairs.json")
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from evaluation.constants import EVAL_DATASET_PATH
from evaluation.exceptions import DatasetLoadError

logger = logging.getLogger(__name__)

_REQUIRED_FIELDS = {"question", "ground_truth", "document_id", "document_title", "tags"}


@dataclass(frozen=True)
class EvalSample:
    """A single ground-truth question-answer pair used for evaluation.

    document_id is empty string in the dataset file and resolved to a real UUID
    by run_evals.py after documents are ingested.
    """

    question: str
    ground_truth: str
    document_id: str
    document_title: str
    tags: tuple[str, ...]


class EvalDatasetLoader:
    """Loads and validates the ground-truth Q&A dataset from a JSON file."""

    def load(self, path: str = EVAL_DATASET_PATH) -> list[EvalSample]:
        """Load all eval samples from the JSON file at the given path.

        Raises:
            DatasetLoadError: If the file is missing, contains invalid JSON,
                uses an unsupported version, or any sample fails validation.
        """
        file_path = Path(path)

        if not file_path.exists():
            raise DatasetLoadError(
                f"Eval dataset not found: {path}. "
                "Run scripts/create_eval_docs.py to generate it."
            )

        try:
            raw = file_path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise DatasetLoadError(
                f"Eval dataset contains invalid JSON: {exc}"
            ) from exc

        if data.get("version") != "1.0":
            raise DatasetLoadError(
                f"Unsupported dataset version: {data.get('version')!r}. Expected '1.0'."
            )

        raw_samples = data.get("samples", [])
        if not raw_samples:
            raise DatasetLoadError("Eval dataset contains no samples.")

        samples = []
        for i, entry in enumerate(raw_samples):
            missing = _REQUIRED_FIELDS - entry.keys()
            if missing:
                raise DatasetLoadError(
                    f"Sample {i} is missing required fields: {sorted(missing)}"
                )

            if not entry["question"].strip():
                raise DatasetLoadError(f"Sample {i} has an empty question.")

            if not entry["ground_truth"].strip():
                raise DatasetLoadError(f"Sample {i} has an empty ground_truth.")

            samples.append(
                EvalSample(
                    question=entry["question"],
                    ground_truth=entry["ground_truth"],
                    document_id=entry["document_id"],
                    document_title=entry["document_title"],
                    tags=tuple(entry["tags"]),
                )
            )

        logger.info(
            "Eval dataset loaded",
            extra={"path": str(path), "sample_count": len(samples)},
        )
        return samples
