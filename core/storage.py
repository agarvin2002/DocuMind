"""
core/storage.py — Thin wrapper around django-storages for file I/O.

Centralises all storage operations so every caller gets consistent error
handling, structured logging, and StorageError re-raising rather than raw
S3/MinIO exceptions propagating up to application code.

Usage:
    from core.storage import StorageClient

    with StorageClient().download_file("documents/2024/01/report.pdf") as f:
        data = f.read()
"""

import logging
from typing import IO

from core.exceptions import StorageError

logger = logging.getLogger(__name__)


def _validate_storage_path(path: str) -> None:
    """
    Reject paths that could escape the storage bucket root.

    S3-compatible APIs generally reject keys with ".." components, but
    defending at the application layer ensures the constraint holds regardless
    of the storage backend (MinIO, LocalStorage, Azure, etc.).

    Args:
        path: Storage-relative path to validate.

    Raises:
        ValueError: if the path contains traversal sequences or is absolute.
    """
    if not path:
        raise ValueError("Storage path must not be empty")
    parts = path.replace("\\", "/").split("/")
    if ".." in parts:
        raise ValueError(f"Storage path contains traversal sequence: {path!r}")
    if path.startswith("/"):
        raise ValueError(f"Storage path must be relative, not absolute: {path!r}")


class StorageClient:
    """
    Wraps django-storages default_storage with consistent error handling.

    Uses default_storage internally so MinIO (development) and AWS S3
    (production) are handled transparently via settings.STORAGES — no raw
    boto3 calls here.
    """

    def download_file(self, path: str) -> IO[bytes]:
        """
        Open a stored file for reading and return a file-like object.

        The caller is responsible for closing the returned object, ideally
        via a context manager:

            with client.download_file(path) as f:
                data = f.read()

        Args:
            path: Storage-relative path as returned by document.file.name.

        Returns:
            An open binary file-like object.

        Raises:
            ValueError: if the path contains traversal sequences.
            StorageError: if the file cannot be opened.
        """
        _validate_storage_path(path)
        from django.core.files.storage import default_storage

        try:
            return default_storage.open(path, "rb")
        except Exception as e:  # noqa: BLE001
            logger.error(
                "Failed to download file from storage",
                extra={"path": path, "error": str(e), "error_type": type(e).__name__},
            )
            raise StorageError(f"Could not open file {path!r} from storage: {e}") from e

    def delete_file(self, path: str) -> None:
        """
        Delete a file from storage.

        Args:
            path: Storage-relative path of the file to delete.

        Raises:
            ValueError: if the path contains traversal sequences.
            StorageError: if the deletion fails.
        """
        _validate_storage_path(path)
        from django.core.files.storage import default_storage

        try:
            default_storage.delete(path)
        except Exception as e:  # noqa: BLE001
            logger.error(
                "Failed to delete file from storage",
                extra={"path": path, "error": str(e), "error_type": type(e).__name__},
            )
            raise StorageError(
                f"Could not delete file {path!r} from storage: {e}"
            ) from e

    def file_exists(self, path: str) -> bool:
        """
        Return True if the file exists in storage, False otherwise.

        Args:
            path: Storage-relative path to check.

        Raises:
            ValueError: if the path contains traversal sequences.
            StorageError: if the existence check itself fails.
        """
        _validate_storage_path(path)
        from django.core.files.storage import default_storage

        try:
            return default_storage.exists(path)
        except Exception as e:  # noqa: BLE001
            logger.error(
                "Failed to check file existence in storage",
                extra={"path": path, "error": str(e), "error_type": type(e).__name__},
            )
            raise StorageError(
                f"Could not check existence of {path!r} in storage: {e}"
            ) from e

    def get_presigned_url(self, path: str, expires_in_seconds: int = 3600) -> str:
        """
        Return a time-limited pre-signed URL for direct client access to a file.

        Useful for generating download links without proxying file bytes through
        the application server.

        Args:
            path: Storage-relative path of the file.
            expires_in_seconds: URL validity window (default 1 hour).

        Raises:
            ValueError: if the path contains traversal sequences.
            StorageError: if the URL cannot be generated.
        """
        _validate_storage_path(path)
        from django.core.files.storage import default_storage

        try:
            return default_storage.url(path)
        except Exception as e:  # noqa: BLE001
            logger.error(
                "Failed to generate presigned URL",
                extra={"path": path, "error": str(e), "error_type": type(e).__name__},
            )
            raise StorageError(
                f"Could not generate presigned URL for {path!r}: {e}"
            ) from e
