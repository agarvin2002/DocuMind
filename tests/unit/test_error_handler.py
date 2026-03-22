"""
Unit tests for Task 7.4 — Structured Error Handling.

Tests cover:
  - DocuMindError subclasses all have code attributes
  - documind_exception_handler returns correct status + code for each exception type
  - Throttled responses include Retry-After header and retry_after body field
  - Unhandled exceptions return 500 without stack trace in body
  - All responses include request_id field
  - DRF ValidationError nested errors are flattened to a single string
"""

from __future__ import annotations

from unittest.mock import MagicMock

from rest_framework.exceptions import (
    AuthenticationFailed,
    MethodNotAllowed,
    NotAuthenticated,
    NotFound,
    ParseError,
    PermissionDenied,
    Throttled,
)
from rest_framework.exceptions import ValidationError as DRFValidationError

from core.error_handler import _flatten_drf_errors, documind_exception_handler
from core.exceptions import (
    DocuMindError,
    EmbeddingError,
    LLMError,
    NotFoundError,
    ProcessingError,
    StorageError,
    ValidationError,
)
from documents.exceptions import (
    DocumentNotFoundError,
    UnsupportedFileTypeError,
)
from query.exceptions import ModelNotAvailableError, NoRelevantChunksError, QueryError

# ---------------------------------------------------------------------------
# Exception code attributes
# ---------------------------------------------------------------------------


def test_documind_error_has_code():
    assert DocuMindError.code == "INTERNAL_ERROR"


def test_not_found_error_code():
    assert NotFoundError.code == "NOT_FOUND"


def test_validation_error_code():
    assert ValidationError.code == "VALIDATION_ERROR"


def test_processing_error_code():
    assert ProcessingError.code == "PROCESSING_ERROR"


def test_storage_error_code():
    assert StorageError.code == "STORAGE_ERROR"


def test_llm_error_code():
    assert LLMError.code == "LLM_ERROR"


def test_embedding_error_code():
    assert EmbeddingError.code == "EMBEDDING_ERROR"


def test_document_not_found_inherits_not_found_code():
    assert DocumentNotFoundError.code == "NOT_FOUND"


def test_unsupported_file_type_overrides_code():
    assert UnsupportedFileTypeError.code == "UNSUPPORTED_FILE_TYPE"


def test_no_relevant_chunks_code():
    assert NoRelevantChunksError.code == "NO_RELEVANT_CHUNKS"


def test_model_not_available_code():
    assert ModelNotAvailableError.code == "MODEL_NOT_AVAILABLE"


def test_query_error_code():
    assert QueryError.code == "QUERY_ERROR"


# ---------------------------------------------------------------------------
# _flatten_drf_errors helper
# ---------------------------------------------------------------------------


def test_flatten_string():
    assert _flatten_drf_errors("bad field") == "bad field"


def test_flatten_list():
    assert _flatten_drf_errors(["error one", "error two"]) == "error one; error two"


def test_flatten_dict():
    result = _flatten_drf_errors({"field": ["required"]})
    assert "required" in result


def test_flatten_nested_dict():
    result = _flatten_drf_errors({"nested": {"field": ["too short"]}})
    assert "too short" in result


# ---------------------------------------------------------------------------
# documind_exception_handler — context helper
# ---------------------------------------------------------------------------


def _make_context():
    """Minimal context dict the handler expects."""
    request = MagicMock()
    request.request_id = "test-request-id"
    return {"request": request}


# ---------------------------------------------------------------------------
# DocuMindError dispatch
# ---------------------------------------------------------------------------


def test_not_found_error_returns_404():
    response = documind_exception_handler(NotFoundError("missing"), _make_context())
    assert response is not None
    assert response.status_code == 404
    assert response.data["code"] == "NOT_FOUND"
    assert response.data["error"] == "missing"


def test_validation_error_returns_400():
    response = documind_exception_handler(ValidationError("bad data"), _make_context())
    assert response is not None
    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION_ERROR"


def test_llm_error_returns_502():
    response = documind_exception_handler(LLMError("model died"), _make_context())
    assert response is not None
    assert response.status_code == 502
    assert response.data["code"] == "LLM_ERROR"


def test_document_not_found_returns_404_with_not_found_code():
    response = documind_exception_handler(DocumentNotFoundError(), _make_context())
    assert response is not None
    assert response.status_code == 404
    assert response.data["code"] == "NOT_FOUND"


def test_unsupported_file_type_returns_422_with_own_code():
    response = documind_exception_handler(UnsupportedFileTypeError(), _make_context())
    assert response is not None
    assert response.status_code == 422
    assert response.data["code"] == "UNSUPPORTED_FILE_TYPE"


def test_no_relevant_chunks_returns_404():
    response = documind_exception_handler(NoRelevantChunksError(), _make_context())
    assert response is not None
    assert response.status_code == 404
    assert response.data["code"] == "NO_RELEVANT_CHUNKS"


def test_model_not_available_returns_400():
    response = documind_exception_handler(ModelNotAvailableError(), _make_context())
    assert response is not None
    assert response.status_code == 400
    assert response.data["code"] == "MODEL_NOT_AVAILABLE"


# ---------------------------------------------------------------------------
# DRF built-in exceptions
# ---------------------------------------------------------------------------


def test_not_authenticated_returns_401():
    response = documind_exception_handler(NotAuthenticated(), _make_context())
    assert response is not None
    assert response.status_code == 401
    # DRF's NotAuthenticated uses "not_authenticated" as its default_code.
    assert "authenticated" in response.data["code"].lower()


def test_authentication_failed_returns_401():
    response = documind_exception_handler(AuthenticationFailed(), _make_context())
    assert response is not None
    assert response.status_code == 401


def test_permission_denied_returns_403():
    response = documind_exception_handler(PermissionDenied(), _make_context())
    assert response is not None
    assert response.status_code == 403


def test_drf_not_found_returns_404():
    response = documind_exception_handler(NotFound(), _make_context())
    assert response is not None
    assert response.status_code == 404
    assert response.data["code"] == "NOT_FOUND"


def test_method_not_allowed_returns_405():
    response = documind_exception_handler(MethodNotAllowed("DELETE"), _make_context())
    assert response is not None
    assert response.status_code == 405
    assert response.data["code"] == "METHOD_NOT_ALLOWED"


def test_drf_validation_error_returns_400_flattened():
    exc = DRFValidationError({"field": ["This field is required."]})
    response = documind_exception_handler(exc, _make_context())
    assert response is not None
    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION_ERROR"
    assert "required" in response.data["error"]


def test_parse_error_returns_400():
    response = documind_exception_handler(ParseError(), _make_context())
    assert response is not None
    assert response.status_code == 400
    assert response.data["code"] == "PARSE_ERROR"


# ---------------------------------------------------------------------------
# Throttled — 429 with Retry-After header
# ---------------------------------------------------------------------------


def test_throttled_returns_429():
    exc = Throttled(wait=30)
    response = documind_exception_handler(exc, _make_context())
    assert response is not None
    assert response.status_code == 429
    assert response.data["code"] == "RATE_LIMIT_EXCEEDED"


def test_throttled_body_has_retry_after_field():
    exc = Throttled(wait=45)
    response = documind_exception_handler(exc, _make_context())
    assert response.data["retry_after"] == 45


def test_throttled_has_retry_after_header():
    exc = Throttled(wait=60)
    response = documind_exception_handler(exc, _make_context())
    assert response["Retry-After"] == "60"


# ---------------------------------------------------------------------------
# Unhandled exception → 500 (no stack trace)
# ---------------------------------------------------------------------------


def test_unhandled_exception_returns_500():
    response = documind_exception_handler(RuntimeError("boom"), _make_context())
    assert response is not None
    assert response.status_code == 500
    assert response.data["code"] == "INTERNAL_ERROR"


def test_unhandled_exception_body_has_no_traceback():
    response = documind_exception_handler(RuntimeError("boom"), _make_context())
    body = str(response.data)
    assert "Traceback" not in body
    assert "RuntimeError" not in body
    assert "boom" not in body


# ---------------------------------------------------------------------------
# All responses include request_id
# ---------------------------------------------------------------------------


def test_all_responses_include_request_id():
    exceptions = [
        NotFoundError(),
        ValidationError(),
        NotAuthenticated(),
        PermissionDenied(),
        Throttled(wait=5),
        DRFValidationError("bad"),
        RuntimeError("crash"),
    ]
    for exc in exceptions:
        response = documind_exception_handler(exc, _make_context())
        assert response is not None
        assert "request_id" in response.data, (
            f"Missing request_id for {type(exc).__name__}"
        )
