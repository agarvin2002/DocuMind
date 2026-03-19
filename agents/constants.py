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
# Sized for local Ollama (llama3.2:3b ≈ 5 tok/s):
#   400 tokens → ~80s generation + ~20s prompt processing → ~100s total
#   600 tokens → ~120s + ~20s → ~140s total
# Both fit within AGENT_LLM_TIMEOUT_SECONDS=200. Production OpenAI is 200 tok/s,
# so these limits are never approached there.
AGENT_SYNTHESIS_MAX_TOKENS: int = 1000   # final synthesis answer
AGENT_SUBQUERY_MAX_TOKENS: int = 1000    # per-sub-question answer
# Sized so qwen2.5:3b (9 tok/s) finishes naturally without truncation:
# 1000 tokens ÷ 9 tok/s ≈ 111s generation + ~19s prompt = ~130s total,
# safely within AGENT_LLM_TIMEOUT_SECONDS=200. Truncation causes Instructor
# to retry, and retry prompts cause models to hallucinate garbage.

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
