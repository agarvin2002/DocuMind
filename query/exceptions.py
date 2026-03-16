"""Query app — custom exceptions."""

from core.exceptions import DocuMindError, ValidationError


class QueryError(DocuMindError):
    """Raised when a Q&A query fails to execute."""
    default_message = "Query execution failed."


class NoRelevantChunksError(QueryError):
    """Raised when the retrieval system finds no relevant context for a question."""
    default_message = "No relevant content found for this question."
    http_status_code = 404


class ModelNotAvailableError(ValidationError):
    """Raised when the caller requests a model that is not configured."""
    default_message = "The requested model is not available."
    http_status_code = 400
