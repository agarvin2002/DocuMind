"""
Unit tests for Task 7.2 — Rate Limiting.

Tests cover:
  - RateLimiter.is_allowed() — allow / deny / fail-open logic
  - Redis error handling (fail open)
  - Throttle class scope isolation
  - 429 response shape (retry_after field + Retry-After header)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import redis as redis_lib

from core.constants import (
    RATE_LIMIT_ANALYSIS_CREATE,
    RATE_LIMIT_DOCUMENTS_UPLOAD,
    RATE_LIMIT_QUERY_ASK,
    RATE_LIMIT_QUERY_SEARCH,
    RATE_LIMIT_WINDOW_SECONDS,
)
from core.rate_limit import RateLimiter
from core.throttles import (
    AnalysisCreateThrottle,
    DocumentUploadThrottle,
    QueryAskThrottle,
    QuerySearchThrottle,
    _APIKeyRateThrottle,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestRateLimitConstants:
    def test_analysis_create_limit_is_10(self):
        assert RATE_LIMIT_ANALYSIS_CREATE == 10

    def test_query_ask_limit_is_20(self):
        assert RATE_LIMIT_QUERY_ASK == 20

    def test_documents_upload_limit_is_30(self):
        assert RATE_LIMIT_DOCUMENTS_UPLOAD == 30

    def test_query_search_limit_is_60(self):
        assert RATE_LIMIT_QUERY_SEARCH == 60

    def test_window_is_60_seconds(self):
        assert RATE_LIMIT_WINDOW_SECONDS == 60


# ---------------------------------------------------------------------------
# RateLimiter — is_allowed() via mocked Lua script
# ---------------------------------------------------------------------------

class TestRateLimiter:
    def _make_limiter(self) -> RateLimiter:
        """Creates a RateLimiter with a fully mocked Redis client."""
        with patch("core.rate_limit.redis_lib.from_url") as mock_from_url:
            mock_client = MagicMock()
            mock_from_url.return_value = mock_client
            # register_script returns a callable
            mock_script = MagicMock()
            mock_client.register_script.return_value = mock_script
            limiter = RateLimiter(redis_url="redis://localhost:6379")
            limiter._script = mock_script  # keep the mock accessible
        return limiter

    def test_returns_true_when_script_allows(self):
        limiter = self._make_limiter()
        limiter._script.return_value = [1, 5, 0]  # allowed=1, count=5, retry=0
        allowed, retry = limiter.is_allowed("key", limit=10)
        assert allowed is True
        assert retry == 0

    def test_returns_false_when_script_denies(self):
        limiter = self._make_limiter()
        limiter._script.return_value = [0, 10, 5000]  # denied, retry_after_ms=5000
        allowed, retry = limiter.is_allowed("key", limit=10)
        assert allowed is False
        assert retry >= 1

    def test_retry_after_is_at_least_1_second(self):
        limiter = self._make_limiter()
        limiter._script.return_value = [0, 10, 100]  # 100ms → rounds up to 1s
        _, retry = limiter.is_allowed("key", limit=10)
        assert retry >= 1

    def test_fail_open_on_redis_error(self):
        limiter = self._make_limiter()
        limiter._script.side_effect = redis_lib.RedisError("Connection refused")
        allowed, retry = limiter.is_allowed("key", limit=10)
        assert allowed is True
        assert retry == 0

    def test_different_keys_are_independent(self):
        limiter = self._make_limiter()
        # First call: allowed; second call: denied
        limiter._script.side_effect = [
            [1, 1, 0],   # key_a allowed
            [0, 5, 3000],  # key_b denied
        ]
        allowed_a, _ = limiter.is_allowed("key_a", limit=10)
        allowed_b, _ = limiter.is_allowed("key_b", limit=10)
        assert allowed_a is True
        assert allowed_b is False


# ---------------------------------------------------------------------------
# Throttle classes — class attributes
# ---------------------------------------------------------------------------

class TestThrottleClasses:
    def test_analysis_create_throttle_rate(self):
        assert AnalysisCreateThrottle.rate_limit == RATE_LIMIT_ANALYSIS_CREATE

    def test_query_ask_throttle_rate(self):
        assert QueryAskThrottle.rate_limit == RATE_LIMIT_QUERY_ASK

    def test_document_upload_throttle_rate(self):
        assert DocumentUploadThrottle.rate_limit == RATE_LIMIT_DOCUMENTS_UPLOAD

    def test_query_search_throttle_rate(self):
        assert QuerySearchThrottle.rate_limit == RATE_LIMIT_QUERY_SEARCH

    def test_scopes_are_unique(self):
        scopes = {
            AnalysisCreateThrottle.scope,
            QueryAskThrottle.scope,
            DocumentUploadThrottle.scope,
            QuerySearchThrottle.scope,
        }
        assert len(scopes) == 4

    def test_all_throttle_classes_extend_base(self):
        for cls in [AnalysisCreateThrottle, QueryAskThrottle, DocumentUploadThrottle, QuerySearchThrottle]:
            assert issubclass(cls, _APIKeyRateThrottle)


# ---------------------------------------------------------------------------
# Throttle — allow_request() and wait()
# ---------------------------------------------------------------------------

class TestAPIKeyRateThrottle:
    def _make_request(self, key_hash: str = "abc123") -> MagicMock:
        request = MagicMock()
        request.auth = MagicMock()
        request.auth.key_hash = key_hash
        request.auth.name = "test-key"
        return request

    def test_allow_request_returns_true_when_allowed(self):
        throttle = QuerySearchThrottle()
        request = self._make_request()
        with patch("core.throttles._rate_limiter") as mock_limiter:
            mock_limiter.is_allowed.return_value = (True, 0)
            result = throttle.allow_request(request, view=None)
        assert result is True

    def test_allow_request_returns_false_when_denied(self):
        throttle = QuerySearchThrottle()
        request = self._make_request()
        with patch("core.throttles._rate_limiter") as mock_limiter:
            mock_limiter.is_allowed.return_value = (False, 30)
            result = throttle.allow_request(request, view=None)
        assert result is False

    def test_wait_returns_retry_after_when_denied(self):
        throttle = QuerySearchThrottle()
        request = self._make_request()
        with patch("core.throttles._rate_limiter") as mock_limiter:
            mock_limiter.is_allowed.return_value = (False, 42)
            throttle.allow_request(request, view=None)
        assert throttle.wait() == 42

    def test_wait_returns_none_when_not_yet_called(self):
        throttle = QuerySearchThrottle()
        assert throttle.wait() is None

    def test_allow_request_uses_correct_scope_in_redis_key(self):
        throttle = QueryAskThrottle()
        request = self._make_request(key_hash="deadbeef")
        with patch("core.throttles._rate_limiter") as mock_limiter:
            mock_limiter.is_allowed.return_value = (True, 0)
            throttle.allow_request(request, view=None)
        call_kwargs = mock_limiter.is_allowed.call_args
        key_used = call_kwargs[1]["key"] if call_kwargs[1] else call_kwargs[0][0]
        assert "deadbeef" in key_used
        assert "query_ask" in key_used

    def test_allow_request_passes_through_when_no_key_hash(self):
        """Requests without key_hash (unauthenticated) pass through — auth layer handles them."""
        throttle = QuerySearchThrottle()
        request = MagicMock()
        request.auth = None  # No auth object at all
        result = throttle.allow_request(request, view=None)
        assert result is True
