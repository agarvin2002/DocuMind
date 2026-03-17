"""
agents/constants.py — Typed constants for the agent pipeline.

All tuning knobs live here. Never hardcode these values inside node functions
or service methods — changing a constant should be a single-line edit.
"""

# Sub-question decomposition
AGENT_SUB_QUESTION_MIN: int = 2
AGENT_SUB_QUESTION_MAX: int = 4

# Retrieval chunk counts
AGENT_RETRIEVAL_K: int = 5      # chunks per sub-question (multi-hop)
AGENT_COMPARISON_K: int = 8     # chunks per document (comparison / contradiction)

# LLM generation limits
AGENT_SYNTHESIS_MAX_TOKENS: int = 1500   # final synthesis answer
AGENT_SUBQUERY_MAX_TOKENS: int = 800     # per-sub-question answer

# LLM sampling — 0.0 = deterministic (good for classification/planning)
AGENT_PLANNER_TEMPERATURE: float = 0.0
AGENT_GENERATION_TEMPERATURE: float = 0.1


# Redis cache key prefixes
AGENT_CLASSIFY_CACHE_PREFIX: str = "documind:agent:classify:v1:"
AGENT_DECOMPOSE_CACHE_PREFIX: str = "documind:agent:decompose:v1:"
AGENT_JOB_RESULT_CACHE_PREFIX: str = "documind:agent:result:v1:"

# Redis cache TTLs (seconds)
AGENT_CACHE_TTL: int = 3600        # classify + decompose results (1 hour)
AGENT_JOB_RESULT_TTL: int = 3600   # completed job result (1 hour)
