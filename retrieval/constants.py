"""
retrieval/constants.py — Named constants for the retrieval layer.

All tuning values live here. Never hardcode these directly inside pipeline,
reranker, or fusion methods — changing a constant should be a single-line edit.

Env-configurable values (retrieval timeout, candidate multiplier) live in
core/settings.py and are referenced via django.conf.settings.
"""

# Maximum number of candidates passed to the CrossEncoderReranker in one call.
# The cross-encoder loads query + chunk pairs into memory together — an unbounded
# input list risks OOM if upstream pipeline logic changes and passes a large pool.
# 100 is generous: the default pool is k * candidate_multiplier = 5 * 3 = 15.
RERANKER_MAX_CANDIDATES: int = 100
