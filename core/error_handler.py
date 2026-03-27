"""
core/error_handler.py — unified DRF exception handler.

Wired via REST_FRAMEWORK["EXCEPTION_HANDLER"] in core/settings.py.
Every exception that escapes any DRF view passes through here.

Standard error envelope:
    {
        "error":      "Human-readable message",
        "code":       "MACHINE_READABLE_CODE",
        "request_id": "abc123"
    }

Guarantees:
  - Stack traces are never leaked to the client.
  - 5xx errors are logged with logger.exception() before responding.
  - Throttled (429) responses include Retry-After header + retry_after body field.
  - DRF ValidationError nested dicts are flattened to a single string.
"""

import logging

from rest_framework import status
from rest_framework.exceptions import (
    AuthenticationFailed,
    MethodNotAllowed,
    NotAcceptable,
    NotAuthenticated,
    NotFound,
    ParseError,
    PermissionDenied,
    Throttled,
)
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from core.exceptions import DocuMindError
from core.middleware import get_current_request_id

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_request_id(context: dict | None) -> str:
    """
    Returns the request ID for the current thread.
    Falls back to the request object on context, then to "-".
    """
    rid = get_current_request_id()
    if rid:
        return rid
    try:
        return context["request"].request_id  # type: ignore[index]
    except (TypeError, KeyError, AttributeError):
        return "-"


def _flatten_drf_errors(detail) -> str:
    """
    Recursively collects all error strings from DRF's nested error structure.
    Returns them joined by "; " as a single human-readable string.
    """
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        return "; ".join(_flatten_drf_errors(item) for item in detail)
    if isinstance(detail, dict):
        return "; ".join(_flatten_drf_errors(v) for v in detail.values())
    return str(detail)


# ---------------------------------------------------------------------------
# Main handler
# ---------------------------------------------------------------------------


def documind_exception_handler(exc: Exception, context: dict) -> Response | None:
    """
    Unified exception handler for all DocuMind API endpoints.

    Registered via REST_FRAMEWORK["EXCEPTION_HANDLER"] in settings.py.
    """
    request_id = _get_request_id(context)

    # --- DocuMind custom exceptions ---
    if isinstance(exc, DocuMindError):
        if exc.http_status_code >= 500:
            logger.exception(
                "Internal server error",
                extra={"code": exc.code, "request_id": request_id},
            )
        return Response(
            {"error": exc.message, "code": exc.code, "request_id": request_id},
            status=exc.http_status_code,
        )

    # --- DRF 401 ---
    if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
        code = "UNAUTHENTICATED"
        # Preserve the specific code from authentication/exceptions.py subclasses.
        detail_code = getattr(getattr(exc, "detail", None), "code", None)
        if detail_code:
            code = str(detail_code)
        return Response(
            {"error": str(exc.detail), "code": code, "request_id": request_id},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    # --- DRF 403 ---
    if isinstance(exc, PermissionDenied):
        code = "PERMISSION_DENIED"
        detail_code = getattr(getattr(exc, "detail", None), "code", None)
        if detail_code:
            code = str(detail_code)
        return Response(
            {"error": str(exc.detail), "code": code, "request_id": request_id},
            status=status.HTTP_403_FORBIDDEN,
        )

    # --- DRF 404 ---
    if isinstance(exc, NotFound):
        return Response(
            {
                "error": "The requested resource was not found.",
                "code": "NOT_FOUND",
                "request_id": request_id,
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # --- DRF 406 ---
    if isinstance(exc, NotAcceptable):
        return Response(
            {
                "error": "The requested content type is not supported.",
                "code": "NOT_ACCEPTABLE",
                "request_id": request_id,
            },
            status=status.HTTP_406_NOT_ACCEPTABLE,
        )

    # --- DRF 405 ---
    if isinstance(exc, MethodNotAllowed):
        return Response(
            {
                "error": "Method not allowed.",
                "code": "METHOD_NOT_ALLOWED",
                "request_id": request_id,
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    # --- DRF 429 with Retry-After ---
    if isinstance(exc, Throttled):
        wait = int(exc.wait) if exc.wait is not None else 0
        response = Response(
            {
                "error": "Rate limit exceeded. Please slow down.",
                "code": "RATE_LIMIT_EXCEEDED",
                "retry_after": wait,
                "request_id": request_id,
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
        response["Retry-After"] = str(wait)
        return response

    # --- DRF ValidationError (400) ---
    if isinstance(exc, DRFValidationError):
        return Response(
            {
                "error": _flatten_drf_errors(exc.detail),
                "code": "VALIDATION_ERROR",
                "request_id": request_id,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # --- DRF ParseError (malformed JSON body) ---
    if isinstance(exc, ParseError):
        return Response(
            {
                "error": "Malformed request body.",
                "code": "PARSE_ERROR",
                "request_id": request_id,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # --- Unhandled exception → 500 (never leak stack trace) ---
    logger.exception(
        "Unhandled exception",
        extra={"exception_type": type(exc).__name__, "request_id": request_id},
    )
    return Response(
        {
            "error": "An unexpected error occurred.",
            "code": "INTERNAL_ERROR",
            "request_id": request_id,
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
