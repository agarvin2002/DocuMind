"""
Request ID middleware.

Attaches a unique ID to every incoming HTTP request and propagates it through
thread-local storage so every log line produced during that request is
automatically stamped with the same ID. Echoes the ID in the X-Request-ID
response header for client-side correlation.
"""

import logging
import threading
import uuid

logger = logging.getLogger(__name__)

# Thread-local storage ensures each concurrent request has its own isolated ID.
_request_id_store = threading.local()


def get_current_request_id() -> str | None:
    """Returns the request ID for the current thread, or None outside an HTTP request."""
    return getattr(_request_id_store, "request_id", None)


class RequestIDMiddleware:
    """
    Generates or forwards a request ID for every HTTP request.

    - Preserves X-Request-ID if the client/load balancer sends one.
    - Otherwise generates a new 12-character hex ID.
    - Stores it in thread-local so all log calls during this request carry it.
    - Echoes it back in the X-Request-ID response header.

    Must be placed early in MIDDLEWARE (after SecurityMiddleware) so all
    subsequent middleware and views have access to the request ID.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]

        _request_id_store.request_id = request_id
        request.request_id = request_id

        response = self.get_response(request)
        response["X-Request-ID"] = request_id

        # Clear after response to prevent bleed into the next request on a reused thread.
        _request_id_store.request_id = None

        return response


class RequestIDFilter(logging.Filter):
    """
    Injects the current request ID into every log record.

    Attach this filter to a handler once in settings.py; all log lines across
    every module automatically receive the request_id field. Falls back to "-"
    outside an HTTP request (Celery tasks, management commands) so the field
    is always present in JSON output.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_current_request_id() or "-"
        return True
