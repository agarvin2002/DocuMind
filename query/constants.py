"""
query/constants.py — query-layer constants.
"""

SEMANTIC_CACHE_SIMILARITY_THRESHOLD: float = 0.92
"""
Cosine similarity threshold for a cache hit (0.0–1.0).
Two queries are considered equivalent when their embeddings have similarity >= 0.92,
which maps to cosine distance <= 0.08 in pgvector's <=> operator.
"""

SEMANTIC_CACHE_TTL_DAYS: int = 7
"""Cached entries older than this are ignored on lookup and cleaned up lazily."""
