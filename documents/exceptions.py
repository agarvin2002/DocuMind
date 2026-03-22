"""
Documents app — custom exceptions.

These inherit from core.exceptions so callers can catch at any level:
    except DocumentNotFoundError  ← catch only document errors
    except NotFoundError           ← catch any "not found" error
    except DocuMindError           ← catch any DocuMind error
"""

from core.exceptions import NotFoundError, ProcessingError, StorageError


class DocumentNotFoundError(NotFoundError):
    """Raised when a Document with the given ID does not exist."""

    default_message = "Document not found."


class DocumentProcessingError(ProcessingError):
    """Raised when a document fails during the ingestion pipeline."""

    default_message = "Failed to process document."


class DocumentUploadError(StorageError):
    """Raised when a file cannot be uploaded to MinIO/S3."""

    default_message = "Failed to upload document file."


class UnsupportedFileTypeError(ProcessingError):
    """Raised when an uploaded file type is not supported (e.g. .exe, .zip)."""

    default_message = "File type is not supported."
    code = "UNSUPPORTED_FILE_TYPE"
