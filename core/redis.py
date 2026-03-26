"""
core/redis.py — Shared Redis connection pool for the entire application.

All modules that need Redis should import get_redis_client() from here instead
of creating their own ConnectionPool. A single pool per process means:
  - Fewer open connections to the Redis server
  - Consistent timeout/config across the codebase
  - One place to change Redis settings

Usage:
    from core.redis import get_redis_client
    conn = get_redis_client()
    conn.set("key", "value")
"""

import threading

import redis as redis_lib
from django.conf import settings

_pool: redis_lib.ConnectionPool | None = None
_lock = threading.Lock()


def get_redis_client() -> redis_lib.Redis:
    """
    Return a Redis client backed by the shared application-wide connection pool.

    The pool is created lazily on the first call (after Django settings load)
    and reused for every subsequent call in the same process.
    """
    global _pool
    if _pool is None:
        with _lock:
            if _pool is None:
                _pool = redis_lib.ConnectionPool.from_url(
                    settings.REDIS_URL,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                )
    return redis_lib.Redis(connection_pool=_pool)
