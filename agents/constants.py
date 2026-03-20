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
# Sized for local Ollama (qwen2.5:3b ≈ 9 tok/s):
#   1000 tokens ÷ 9 tok/s ≈ 111s generation + ~19s prompt = ~130s total,
#   safely within AGENT_LLM_TIMEOUT_SECONDS=200. Truncation causes Instructor
#   to retry, and retry prompts cause models to hallucinate garbage.
# Production OpenAI is 200 tok/s, so these limits are never approached there.
AGENT_SYNTHESIS_MAX_TOKENS: int = 1000   # final synthesis answer
AGENT_SUBQUERY_MAX_TOKENS: int = 1000    # per-sub-question answer

# Planning step token limits — smaller because outputs are short structured JSON,
# not prose. Classifier returns a 3-field schema; decomposer returns a list of strings.
# 200 / 400 tokens is generous for these schemas — keeps latency low on local models.
AGENT_CLASSIFY_MAX_TOKENS: int = 200
AGENT_DECOMPOSE_MAX_TOKENS: int = 400

# Instructor structured output retry count.
# Intentionally 0 — Instructor retries multiply latency (each retry = full LLM call).
# With local Ollama, 3 retries = 3× the timeout. Schema issues should be fixed at
# the prompt level, not retried at runtime.
AGENT_STRUCTURED_LLM_MAX_RETRIES: int = 0

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
