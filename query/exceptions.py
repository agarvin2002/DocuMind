"""Query app — custom exceptions."""

from core.exceptions import DocuMindError, LLMError


class QueryError(DocuMindError):
    """Raised when a Q&A query fails to execute."""
    default_message = "Query execution failed."


class NoRelevantChunksError(QueryError):
    """Raised when the retrieval system finds no relevant context for a question."""
    default_message = "No relevant content found for this question."
    http_status_code = 404


class AnswerGenerationError(LLMError):
    """Raised when the LLM fails to generate an answer."""
    default_message = "Failed to generate an answer."
