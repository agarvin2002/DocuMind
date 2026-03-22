"""
core/constants.py — project-wide constants.

Rate limit values are defined here so they live in one place,
are importable by throttle classes and tests, and can be adjusted
without touching view or throttle code.
"""

# ---------------------------------------------------------------------------
# Rate limiting — requests per minute per API key, per endpoint tier
# ---------------------------------------------------------------------------

RATE_LIMIT_ANALYSIS_CREATE: int = 10
"""POST /api/v1/analysis/ — expensive agent pipeline (LLM + multi-hop retrieval)."""

RATE_LIMIT_QUERY_ASK: int = 20
"""POST /api/v1/query/ask/ — LLM generation + streaming."""

RATE_LIMIT_DOCUMENTS_UPLOAD: int = 30
"""POST /api/v1/documents/ — S3 upload + Celery task dispatch."""

RATE_LIMIT_QUERY_SEARCH: int = 60
"""POST /api/v1/query/search/ — retrieval only, no LLM call."""

RATE_LIMIT_WINDOW_SECONDS: int = 60
"""Sliding window size. All tiers share a 60-second window."""

RATE_LIMIT_REDIS_TTL_BUFFER: int = 5
"""Extra seconds added to the Redis key TTL to prevent expiry at the window edge."""
