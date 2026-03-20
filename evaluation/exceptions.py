from core.exceptions import DocuMindError


class EvaluationError(DocuMindError):
    """Base for all evaluation framework failures."""

    http_status_code = 500


class DatasetLoadError(EvaluationError):
    """Raised when the Q&A dataset file is missing, contains invalid JSON, or fails schema validation."""

    http_status_code = 422


class MetricComputeError(EvaluationError):
    """Raised when the RAGAS judge LLM fails to score a batch of samples."""

    http_status_code = 502


class BaselineError(EvaluationError):
    """Raised when the naive baseline system fails to produce an answer for a sample."""

    http_status_code = 500
