# Testing

## Running the Tests

```bash
# All unit tests (244 tests, no Docker services needed)
uv run pytest tests/unit/ -v

# Run all tests (unit + integration — requires docker compose up -d)
uv run pytest -v

# Run a specific test file
uv run pytest tests/unit/test_retrieval.py -v

# Run tests matching a keyword
uv run pytest -k "hybrid" -v
uv run pytest -k "semantic_cache" -v

# Coverage report
uv run pytest tests/unit/ --cov=. --cov-report=html
open htmlcov/index.html

# Lint check (CI standard — zero tolerance)
uv run ruff check .
uv run ruff format --check .
```

---

## Test Structure

```
tests/
├── fakes.py                       # Shared test doubles — import from any test file
├── conftest.py                    # Pytest fixtures available to all tests
│
├── unit/                          # 200+ tests, no external services needed
│   ├── test_ingestion.py          # IngestionPipeline, HierarchicalChunker, PDF parser
│   ├── test_retrieval.py          # HybridFusion, CrossEncoderReranker, VectorStore, BM25
│   ├── test_semantic_cache.py     # Cache lookup, threshold math, TTL logic, fail-open
│   ├── test_generation.py         # SSE event builders, FallbackLLMClient, citation extraction
│   ├── test_agent_graph.py        # All 10 node functions + 4 routing functions
│   ├── test_agent_executor.py     # Singleton pattern, double-checked locking
│   ├── test_agent_schemas.py      # ComplexityClassification, QueryDecomposition Pydantic models
│   ├── test_agent_tools.py        # RetrievalTool wrapping and error propagation
│   ├── test_agent_prompts.py      # Prompt key lookup and content validation
│   ├── test_query_planner.py      # QueryPlanner classify + decompose with FakeStructuredLLMClient
│   ├── test_structured_llm.py     # StructuredLLMClient Instructor integration
│   ├── test_analysis_views.py     # 202 Accepted, job creation, status polling
│   ├── test_analysis_models.py    # AnalysisJob status transitions
│   ├── test_analysis_services.py  # create_analysis_job, mark_job_* functions
│   ├── test_analysis_tasks.py     # Celery task execution paths (success + failure)
│   ├── test_analysis_exceptions.py # AnalysisJobNotFoundError, RetrievalAgentError
│   ├── test_api_key_auth.py       # Authentication backend, hash verification, revocation
│   ├── test_rate_limit.py         # Lua script behavior, fail-open on Redis error
│   ├── test_error_handler.py      # DRF exception handler — all HTTP status codes
│   ├── test_serializers.py        # Request validation, edge cases
│   ├── test_selectors.py          # get_document_by_id, get_job_by_id
│   ├── test_models.py             # Document, DocumentChunk model queries
│   ├── test_evaluation_adapters.py    # FullSystemAdapter, NaiveBaselineAdapter
│   ├── test_evaluation_constants.py   # Threshold values, metric names
│   ├── test_evaluation_datasets.py    # QA pair loading and validation
│   ├── test_evaluation_exceptions.py  # EvaluationError, MetricComputeError
│   ├── test_evaluation_harness.py     # EvaluationHarness comparison logic
│   ├── test_evaluation_metrics.py     # RAGASScorer with FakeRAGScorer
│   ├── test_evaluation_protocols.py   # Protocol structural compliance
│   └── test_evaluation_reports.py     # JSON and Markdown report generation
│
├── integration/                   # Requires running: docker compose up -d
│   ├── test_document_upload.py    # Full upload → Celery → poll → ready flow
│   └── test_health.py             # Health check with real PostgreSQL + Redis
│
└── evals/                         # RAGAS evaluation (requires running server + LLM)
    └── run_evals.py
```

---

## Testing Philosophy: Protocol Fakes, Not Mocks

This is the most important architectural decision in the test suite.

Every pipeline module accepts its dependencies via constructor injection using structural Protocols (`typing.Protocol`). A class satisfies a Protocol simply by having the right method signatures — no inheritance, no registration needed.

This means any test can inject a `Fake` instead of the real implementation, without touching `unittest.mock.patch`:

```python
# The real pipeline
pipeline = RetrievalPipeline(
    vector_store=VectorStore(),
    bm25_index=BM25Index(),
    fusion=HybridFusion(),
    reranker=CrossEncoderReranker(),
)

# In tests — same constructor, different dependencies
pipeline = RetrievalPipeline(
    vector_store=FakeVectorStore(results=sample_chunks),
    bm25_index=FakeBM25Index(results=[]),
    fusion=HybridFusion(),   # real one is fine — it's pure logic, no I/O
    reranker=FakeCrossEncoder(),
)
```

**Why this matters:**

- **Refactoring-safe:** rename a method → update the fake → tests still compile. With `MagicMock`, renaming a method silently passes because `MagicMock` accepts any attribute access.
- **Fast:** no subprocess, no network, no filesystem — unit tests complete in seconds.
- **Readable:** `FakeEmbedder` is 15 explicit lines of behavior. `MagicMock()` is magic.
- **No patching paths:** `@patch("ingestion.pipeline.SentenceTransformerEmbedder")` breaks when the module is renamed. Constructor injection has no implicit module paths.

---

## The `tests/fakes.py` File

Six shared test doubles used across the test suite:

**`FakeLLMProvider(tokens, should_fail)`** — satisfies `LLMProviderPort`
- `tokens` — list of strings to yield from `stream()`, one at a time
- `should_fail=True` — raises `AnswerGenerationError` on `stream()` call
- `call_count` — verify the provider was called the expected number of times
- Used in: `test_generation.py`, `test_analysis_tasks.py`

**`FakeStructuredLLMClient(should_fail)`** — satisfies `StructuredLLMPort`
- Returns pre-built Pydantic models: `ComplexityClassification(workflow_type="multi_hop")`, `QueryDecomposition(sub_questions=["sub q 1", "sub q 2"])`, `SynthesizedAnswer`
- `should_fail=True` — raises `AnswerGenerationError` for error-path testing
- `last_response_model` — inspect which Pydantic model was requested
- Used in: `test_query_planner.py`, `test_agent_graph.py`

**`FakeRetrievalTool(chunks, should_fail)`** — satisfies `RetrievalToolPort`
- Returns a preset list of `ChunkSearchResult` objects
- `should_fail=True` — raises `RetrievalAgentError`
- `call_count` — verify how many retrievals the agent performed (important for multi-hop tests)
- Used in: `test_agent_graph.py`, `test_agent_tools.py`

**`FakeRAGSystem(answer, contexts, should_fail)`** — satisfies `RAGSystemPort`
- Returns a fixed `(answer, contexts)` tuple for evaluation harness tests
- Used in: `test_evaluation_harness.py`, `test_evaluation_adapters.py`

**`FakeSemanticCache(hit_answer)`** — satisfies `SemanticCachePort`
- `hit_answer=None` — simulates a cache miss (query proceeds to retrieval + LLM)
- `hit_answer={"answer": "...", "citations": [...]}` — simulates a cache hit
- `store_calls` — inspect what was written to the cache after a successful query
- Used in: `test_semantic_cache.py`, `test_generation.py`

**`FakeRAGScorer(scores, should_fail)`** — satisfies `RAGScorerPort`
- Returns fixed metric scores `{faithfulness, answer_relevancy, context_recall}`
- `should_fail=True` — raises `MetricComputeError`
- Used in: `test_evaluation_harness.py`, `test_evaluation_metrics.py`

---

## Writing New Unit Tests

The pattern used throughout the test suite — no Django, no `@pytest.mark.django_db`, no mocks:

```python
# tests/unit/test_retrieval.py

def test_hybrid_fusion_scores_chunk_appearing_in_both_lists_higher():
    """A chunk returned by both vector and BM25 search should outscore one from a single source."""
    from retrieval.hybrid import HybridFusion
    from retrieval.schemas import ChunkSearchResult

    chunk_in_both = ChunkSearchResult(chunk_id="a", score=0.9, document_title="Doc", ...)
    chunk_vector_only = ChunkSearchResult(chunk_id="b", score=0.8, document_title="Doc", ...)

    fusion = HybridFusion()
    result = fusion.fuse(
        vector_results=[chunk_in_both, chunk_vector_only],
        bm25_results=[chunk_in_both],  # "a" appears in both lists
        k=2,
    )

    assert result[0].chunk_id == "a"          # higher RRF score
    assert result[0].score > result[1].score
```

```python
# tests/unit/test_agent_graph.py

def test_classify_query_node_routes_to_simple_on_simple_question():
    """classify_query_node should set workflow_type=simple for direct factual questions."""
    from agents.graph import classify_query_node
    from agents.schemas import AgentState
    from tests.fakes import FakeStructuredLLMClient

    fake_planner = FakeQueryPlanner(workflow_type="simple")  # pre-configured response
    state = AgentState(
        job_id="test-job",
        question="What is the effective date of this contract?",
        document_ids=["doc-1"],
        workflow_type="multi_hop",  # user specified multi_hop
    )

    result = classify_query_node(state, planner=fake_planner)

    assert result["workflow_type"] == "simple"  # classifier overrode user's choice
    assert result.get("error") is None
```

The key rule: if a test requires a real database, it belongs in `tests/integration/`, not `tests/unit/`.

---

## Integration Tests

Integration tests require all Docker Compose services running:

```bash
docker compose up -d
uv run pytest tests/integration/ -v
```

Two tests:

**`test_document_upload.py`** — covers the complete ingestion lifecycle:
- Upload a real PDF via `POST /api/v1/documents/`
- Assert the response is `201 Created` with `status=pending`
- Poll `GET /api/v1/documents/{id}/` until `status=ready` or timeout
- Assert `chunk_count > 0` — chunks were created in PostgreSQL
- Assert the BM25 index exists in Redis

**`test_health.py`** — covers the health check endpoint:
- `GET /api/v1/health/` with real PostgreSQL and Redis running → `200 OK`
- Verifies `checks.postgres == "ok"` and `checks.redis == "ok"`

These are the tests that catch "the code works in unit tests but fails when the real database is involved." The integration tests are deliberately few — they're slow and require infrastructure. Everything that can be tested with fakes should be.

---

## RAGAS Evaluations

RAGAS measures retrieval and generation quality against a ground-truth Q&A dataset. It is not a unit test — it is a quality benchmark.

**What it measures:**

| Metric | What it catches |
|--------|----------------|
| `faithfulness` | Is the generated answer supported by the retrieved chunks? Catches hallucination. |
| `answer_relevancy` | Does the answer actually address the question? Catches vague non-answers. |
| `context_recall` | Did retrieval find all the information needed to answer? Catches retrieval gaps. |

**How to run:**

```bash
# Prerequisites: docker compose up -d AND Django runserver + Celery worker running
uv run python tests/evals/run_evals.py

# Quick check with 3 samples (faster — good for local iteration)
uv run python tests/evals/run_evals.py --dry-run

# Force re-run (ignore cached results from previous run)
uv run python tests/evals/run_evals.py --no-cache
```

The evaluator:
1. Loads Q&A pairs from `data/eval/qa_pairs.json`
2. Ingests three test PDFs (ai_concepts, product_spec, science_report) if not already present
3. Runs every question through the full DocuMind pipeline
4. Runs the same questions through a **naive BM25-only baseline** (no vector search, no reranker)
5. Computes RAGAS scores for both
6. Compares: the full pipeline must beat the baseline by **≥20%** on all three metrics

**Pass threshold:** A run PASSES (exit code 0) if the full pipeline beats the BM25-only baseline by ≥20% on faithfulness, answer_relevancy, and context_recall. FAILS (exit code 1) if any metric falls below that threshold.

**Results are cached in Redis** by dataset hash — running the same dataset twice skips the LLM calls and returns the cached scores immediately.

**Reports** are written to the `eval_results/` directory as JSON and Markdown after each run.

**Requires:** `OPENAI_API_KEY` or `OLLAMA_ENABLED=true` (OpenAI produces better RAGAS scores; Ollama is acceptable for local development).

---

## CI Pipeline

Every push to `main` and every pull request triggers two jobs:

**Job 1: `lint`**
```yaml
- uv run ruff check .
```
Zero tolerance. The PR is blocked if any lint error exists.

**Job 2: `unit-tests`**

Services spun up as GitHub Actions service containers:
- PostgreSQL 16 with pgvector (`pgvector/pgvector:pg16`)
- Redis 7

Steps:
```bash
uv sync --dev
uv run python manage.py makemigrations --check --dry-run   # fail if uncommitted migrations
uv run python manage.py migrate
uv run pytest tests/unit/ -v
```

The `makemigrations --check --dry-run` step catches a common mistake: changing a model but forgetting to generate a migration. This would silently pass all tests but break production deployment.

**What CI does NOT run:**
- Integration tests (require Docker services beyond GitHub Actions service containers)
- RAGAS evaluations (require a running Django server and LLM API access)

RAGAS evaluations run on a separate schedule: weekly via `.github/workflows/eval.yml` on Monday at 06:00 UTC. Results are uploaded as GitHub Actions artifacts and compared against the previous run to detect regressions.
