"""
Authentication exceptions.

Inherit from DRF's own exception hierarchy so DRF's exception handler
pipeline can translate them to HTTP responses automatically.
"""

from rest_framework.exceptions import AuthenticationFailed, PermissionDenied


class AuthenticationError(AuthenticationFailed):
    """Raised when no API key is provided, or the key is not recognised."""

    default_detail = "Authentication required."
    default_code = "UNAUTHENTICATED"


class InvalidAPIKeyError(PermissionDenied):
    """Raised when an API key is found in the DB but has been revoked."""

    default_detail = "Invalid or inactive API key."
    default_code = "INVALID_API_KEY"
