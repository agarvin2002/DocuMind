"""
core/throttles.py — per-endpoint DRF throttle classes.

Each class maps to one endpoint tier with its own rate limit.
Apply via throttle_classes = [XxxThrottle] on each view class.
Do NOT use DEFAULT_THROTTLE_CLASSES — endpoints have different limits.

Redis key format: ratelimit:{key_hash}:{scope}
The scope is a stable string (not a URL) so renaming an endpoint
does not lose historical rate-limit state.
"""

import logging

from rest_framework.throttling import BaseThrottle

from core.constants import (
    RATE_LIMIT_ANALYSIS_CREATE,
    RATE_LIMIT_DOCUMENTS_UPLOAD,
    RATE_LIMIT_QUERY_ASK,
    RATE_LIMIT_QUERY_SEARCH,
    RATE_LIMIT_WINDOW_SECONDS,
)
from core.rate_limit import RateLimiter

logger = logging.getLogger(__name__)

# One RateLimiter instance per process — shares the Redis connection pool.
_rate_limiter = RateLimiter()


class _APIKeyRateThrottle(BaseThrottle):
    """
    Base throttle for all DocuMind endpoints.

    Subclasses must set:
        rate_limit: int   — max requests allowed per window
        scope:      str   — stable identifier used in the Redis key
    """

    rate_limit: int = 60
    scope: str = "default"

    def allow_request(self, request, view) -> bool:
        # Unauthenticated requests are already rejected by permissions.
        # This guard handles tests that bypass auth.
        if not hasattr(request.auth, "key_hash"):
            return True

        redis_key = f"ratelimit:{request.auth.key_hash}:{self.scope}"
        allowed, retry_after = _rate_limiter.is_allowed(
            key=redis_key,
            limit=self.rate_limit,
            window_seconds=RATE_LIMIT_WINDOW_SECONDS,
        )

        if not allowed:
            self._retry_after = retry_after
            logger.warning(
                "Rate limit exceeded",
                extra={
                    "scope": self.scope,
                    "key_name": getattr(request.auth, "name", "unknown"),
                    "retry_after": retry_after,
                },
            )

        return allowed

    def wait(self) -> float | None:
        return getattr(self, "_retry_after", None)


class AnalysisCreateThrottle(_APIKeyRateThrottle):
    """POST /api/v1/analysis/ — expensive agent pipeline."""

    rate_limit = RATE_LIMIT_ANALYSIS_CREATE
    scope = "analysis_create"


class QueryAskThrottle(_APIKeyRateThrottle):
    """POST /api/v1/query/ask/ — LLM streaming."""

    rate_limit = RATE_LIMIT_QUERY_ASK
    scope = "query_ask"


class DocumentUploadThrottle(_APIKeyRateThrottle):
    """POST /api/v1/documents/ — S3 upload + Celery dispatch."""

    rate_limit = RATE_LIMIT_DOCUMENTS_UPLOAD
    scope = "documents_upload"


class QuerySearchThrottle(_APIKeyRateThrottle):
    """POST /api/v1/query/search/ — retrieval only."""

    rate_limit = RATE_LIMIT_QUERY_SEARCH
    scope = "query_search"
