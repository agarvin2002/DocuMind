"""
core/rate_limit.py — Redis sorted-set sliding window rate limiter.

Algorithm (runs atomically via a Lua script on Redis):
  1. Remove all entries older than (now - window) from the ZSET.
  2. Count remaining entries — if at or above the limit, deny.
  3. Add the current request (score = now_ms, member = unique UUID).
  4. Refresh the key TTL.
  5. Return allowed=True.

Why a Lua script?
  Redis is single-threaded. A Lua script executes as one atomic unit —
  no other command can interleave between the ZREMRANGEBYSCORE and ZADD.
  Without atomicity, two concurrent requests could both read count=limit-1
  and both succeed when only one should have been allowed.

Why fail open on Redis error?
  A Redis outage should not bring down the API. Rate limiting is a
  quality-of-service concern; availability is more important.
"""

import logging
import time
import uuid
from typing import cast

import redis as redis_lib
from django.conf import settings

from core.constants import RATE_LIMIT_REDIS_TTL_BUFFER, RATE_LIMIT_WINDOW_SECONDS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lua script
# KEYS[1]  — the rate-limit key (one per API key × endpoint scope)
# ARGV[1]  — now_ms        (current Unix time in milliseconds)
# ARGV[2]  — window_start  (now_ms - window_ms)
# ARGV[3]  — limit         (max requests allowed in the window)
# ARGV[4]  — ttl_seconds   (key expiry)
# ARGV[5]  — request_id    (unique member to avoid ZADD score collisions)
#
# Returns: {allowed (0|1), current_count, retry_after_ms}
# ---------------------------------------------------------------------------
_LUA_SCRIPT = """
local key          = KEYS[1]
local now_ms       = tonumber(ARGV[1])
local window_start = tonumber(ARGV[2])
local limit        = tonumber(ARGV[3])
local ttl          = tonumber(ARGV[4])
local request_id   = ARGV[5]

-- 1. Evict stale entries (outside the window).
redis.call("ZREMRANGEBYSCORE", key, "-inf", window_start - 1)

-- 2. Count entries in the current window.
local current = redis.call("ZCARD", key)

-- 3. Deny if at or above the limit.
if current >= limit then
    local oldest = redis.call("ZRANGE", key, 0, 0, "WITHSCORES")
    local oldest_score = tonumber(oldest[2]) or now_ms
    local retry_after_ms = (oldest_score + (ttl * 1000)) - now_ms
    return {0, current, retry_after_ms}
end

-- 4. Record this request.
redis.call("ZADD", key, now_ms, request_id)

-- 5. Refresh TTL.
redis.call("EXPIRE", key, ttl)

return {1, current + 1, 0}
"""


class RateLimiter:
    """
    Sliding window rate limiter backed by a Redis sorted set.

    Instantiate once at module level (in core/throttles.py) so the
    Redis connection pool is shared across all requests in the process.
    """

    def __init__(self, redis_url: str | None = None) -> None:
        url = redis_url or settings.REDIS_URL
        # socket_connect_timeout and socket_timeout mirror core/redis.py so that
        # a Redis hang blocks requests for at most 2 seconds instead of indefinitely.
        # Without these, a Redis outage stalls every authenticated request.
        self._client = redis_lib.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        self._script = self._client.register_script(_LUA_SCRIPT)

    def is_allowed(
        self,
        key: str,
        limit: int,
        window_seconds: int = RATE_LIMIT_WINDOW_SECONDS,
    ) -> tuple[bool, int]:
        """
        Returns (allowed, retry_after_seconds).
        retry_after_seconds is 0 when allowed is True.
        """
        now_ms = int(time.time() * 1000)
        window_start_ms = now_ms - (window_seconds * 1000)
        ttl = window_seconds + RATE_LIMIT_REDIS_TTL_BUFFER
        request_id = uuid.uuid4().hex

        try:
            result = cast(
                list[int],
                self._script(
                    keys=[key],
                    args=[now_ms, window_start_ms, limit, ttl, request_id],
                ),
            )
        except redis_lib.RedisError as exc:
            # Fail open: prefer availability over strict rate-limiting during
            # a Redis outage.
            logger.error(
                "Rate limiter Redis error — failing open",
                extra={"error": str(exc), "key": key},
            )
            return (True, 0)

        allowed = bool(result[0])
        if allowed:
            return (True, 0)

        retry_after_ms = int(result[2]) if result[2] else 0
        retry_after_seconds = max(1, (retry_after_ms // 1000) + 1)
        return (False, retry_after_seconds)
