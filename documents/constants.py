"""
documents/constants.py — Named constants for the documents app.

All values that appear in more than one module (services.py and selectors.py)
or that may need tuning live here — one place to change, zero risk of drift.
"""

# BM25 index Redis cache key prefix.
# Bump this to "documind:bm25:v2:..." if BM25 tokenization logic changes
# (e.g. stemming or stopword removal is added). Old v1 keys will be ignored
# and rebuilt from DB on first query rather than returning stale indexes.
BM25_CACHE_KEY_PREFIX: str = "documind:bm25:v1"

# BM25 index Redis TTL — 7 days in seconds.
# After expiry the index is transparently rebuilt from DocumentChunk rows,
# so this is a performance hint, not a correctness constraint.
BM25_INDEX_TTL_SECONDS: int = 604_800
