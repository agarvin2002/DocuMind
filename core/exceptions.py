"""
Core exceptions — base classes for all DocuMind errors.

Every custom exception inherits from DocuMindError and declares an
http_status_code so views can return the correct HTTP response without
if/elif chains.

    from core.exceptions import NotFoundError, ValidationError
"""


class DocuMindError(Exception):
    """Base class for all DocuMind exceptions."""

    default_message = "An unexpected error occurred."
    http_status_code: int = 500
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)


class NotFoundError(DocuMindError):
    """Raised when a requested resource does not exist."""

    default_message = "The requested resource was not found."
    http_status_code = 404
    code = "NOT_FOUND"


class ValidationError(DocuMindError):
    """Raised when input data fails validation."""

    default_message = "The provided data is invalid."
    http_status_code = 400
    code = "VALIDATION_ERROR"


class ProcessingError(DocuMindError):
    """Raised when document processing fails (parsing, chunking, embedding)."""

    default_message = "Document processing failed."
    http_status_code = 422
    code = "PROCESSING_ERROR"


class StorageError(DocuMindError):
    """Raised when file upload to S3/MinIO fails."""

    default_message = "File storage operation failed."
    http_status_code = 503
    code = "STORAGE_ERROR"


class LLMError(DocuMindError):
    """Raised when an LLM API call fails."""

    default_message = "LLM request failed."
    http_status_code = 502
    code = "LLM_ERROR"


class EmbeddingError(DocuMindError):
    """Raised when generating vector embeddings fails."""

    default_message = "Failed to generate embeddings."
    http_status_code = 502
    code = "EMBEDDING_ERROR"
