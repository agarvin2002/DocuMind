# Metric pass/fail thresholds — from ROADMAP.md Phase 6 definition of done.
# Changing these values affects the PASS/FAIL verdict in every eval run.
FAITHFULNESS_THRESHOLD: float = 0.85
ANSWER_RELEVANCY_THRESHOLD: float = 0.80
CONTEXT_RECALL_THRESHOLD: float = 0.75

# Our system must beat the naive vector-only baseline by at least this percentage
# on every metric for the eval run to be considered a PASS.
BASELINE_IMPROVEMENT_MIN_PCT: float = 20.0

# Eval dataset
EVAL_DATASET_PATH: str = "data/eval/qa_pairs.json"
EVAL_DATASET_SIZE: int = 50

# Redis cache — eval runs are expensive (50 LLM calls × 2 systems).
# Cache by dataset+config hash so re-runs are free until the dataset or config changes.
EVAL_CACHE_PREFIX: str = "documind:eval:result:v1:"
EVAL_CACHE_TTL: int = 86400  # 24 hours

# RAGAS judge LLM — this is the model that scores our outputs, not the model
# under test. gpt-4o-mini is accurate enough for scoring and much cheaper than gpt-4o.
RAGAS_LLM_MODEL: str = "gpt-4o-mini"
RAGAS_JUDGE_TEMPERATURE: float = 0.0  # deterministic scoring, not creative
RAGAS_JUDGE_MAX_TOKENS: int = 1024

# Retrieval — both systems use the same k so the comparison is fair.
EVAL_SYSTEM_K: int = 5    # chunks returned by full hybrid pipeline
EVAL_BASELINE_K: int = 5  # chunks returned by naive vector-only baseline

# Concurrent sample evaluation — same ThreadPoolExecutor pattern as retrieval/pipeline.py.
# 5 workers keeps OpenAI rate limits comfortable while saving ~5× wall-clock time vs serial.
EVAL_MAX_WORKERS: int = 5
