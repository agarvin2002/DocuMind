# Development Setup

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.12 | `brew install python@3.12` (macOS) or [python.org](https://python.org) |
| Docker Desktop | Latest | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/) |
| uv | Latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

Nothing else. `uv` manages the virtualenv and all Python dependencies — no `pip`, no `poetry`, no `virtualenv` commands needed.

---

## Environment Variables

Copy the template and fill it in:

```bash
cp .env.example .env
```

### Required to start (minimum viable .env)

```bash
# 1. Generate a Django secret key
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(50))"

# 2. Add these to .env (values match docker-compose.yml defaults)
DATABASE_URL=postgresql://documind:documind@localhost:5432/documind
REDIS_URL=redis://localhost:6379
AWS_ACCESS_KEY_ID=documind
AWS_SECRET_ACCESS_KEY=documind123
AWS_STORAGE_BUCKET_NAME=documind-documents
AWS_S3_ENDPOINT_URL=http://localhost:9000

# 3. Local LLM (no API key needed)
OLLAMA_ENABLED=true
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen2.5:3b
AGENT_LLM_PROVIDER=ollama
```

### Optional: cloud LLM providers

```bash
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-5

# AWS Bedrock (separate from the S3/MinIO credentials above)
BEDROCK_ENABLED=false
BEDROCK_AWS_ACCESS_KEY_ID=...
BEDROCK_AWS_SECRET_ACCESS_KEY=...
BEDROCK_AWS_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
```

### Logging

```bash
# Local development — human-readable output in your terminal
LOG_LEVEL=DEBUG
LOG_FORMAT=verbose

# Staging/production — structured JSON for Datadog, CloudWatch, etc.
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### LLM tuning (defaults work fine)

| Variable | Default | When to change |
|----------|---------|----------------|
| `DOCUMIND_LLM_TEMPERATURE` | `0.1` | Raise to 0.5–0.7 for creative tasks; keep low for factual Q&A |
| `DOCUMIND_LLM_MAX_TOKENS` | `1024` | Raise if answers are cut off mid-sentence |
| `DOCUMIND_LLM_TIMEOUT_SECONDS` | `90.0` | Fine for Ollama; reduce to 30.0 for OpenAI/Anthropic (they're faster) |
| `DOCUMIND_MAX_CONTEXT_TOKENS` | `6000` | Token budget for all chunks sent to LLM; raise if the LLM supports longer context |
| `AGENT_LLM_TIMEOUT_SECONDS` | `200.0` | Agent non-streaming calls take 60–200s on local hardware |

### LangSmith observability (optional)

```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__...
LANGCHAIN_PROJECT=documind
```

When `LANGCHAIN_TRACING_V2=false`, the `@traceable` decorators on all LLM providers are no-ops — zero performance impact.

---

## Docker Compose Services

```bash
docker compose up -d
```

| Service | Port | Purpose | Dashboard |
|---------|------|---------|-----------|
| `postgres` | 5432 | PostgreSQL 16 + pgvector — app database + vector embeddings | — |
| `redis` | 6379 | Redis 7 — Celery task queue + semantic cache + rate limits | — |
| `flower` | 5555 | Celery monitoring — task status, worker health, queue depth | [localhost:5555](http://localhost:5555) (admin / change-me) |
| `ollama` | 11434 | Local LLM runtime — no API key, free | — |
| `minio` | 9000/9001 | Local S3 — stores uploaded PDF files | [localhost:9001](http://localhost:9001) (documind / documind123) |

All five services have health checks. Wait until they're healthy before running Django:

```bash
docker compose ps   # check STATUS column — "healthy" means ready
```

---

## One-Time Setup

Run these once after the first `docker compose up -d`. After that, you never need to run them again unless you delete the Docker volumes.

```bash
# 1. Create the MinIO bucket where uploaded files will be stored
docker compose exec minio mc alias set local http://localhost:9000 documind documind123
docker compose exec minio mc mb local/documind-documents

# 2. Pull the Ollama model (~2GB download — takes a few minutes)
docker compose exec ollama ollama pull qwen2.5:3b

# 3. Run Django database migrations
uv run python manage.py migrate
```

---

## Running the Application

The application needs three processes. Open three terminal windows:

**Terminal 1 — Django web server:**
```bash
uv run python manage.py runserver
# → http://localhost:8000
```

**Terminal 2 — Celery worker** (ingestion + analysis tasks):
```bash
uv run celery -A core worker --loglevel=info
```

**Terminal 3 — (optional) watch logs:**
The Flower dashboard at [localhost:5555](http://localhost:5555) shows all Celery task state. No third terminal needed unless you want live Celery logs in your terminal too.

---

## Creating an API Key

```bash
uv run python manage.py create_api_key dev-key
# → API key created: dm_aBcDeFgHiJkLmNoPqRsTuVwXyZ123456  (shown once)
```

The raw key is printed exactly once and never stored — only a SHA-256 hash is kept in the database. Store it somewhere safe. If you lose it, create a new one and deactivate the old one via Django admin (`/admin/authentication/apikey/`).

---

## Complete Smoke Test

Copy-paste these commands in order after setup. Replace `dm_xxxx` with your actual API key and update the doc UUID from each response.

```bash
# 1. Upload a document
curl -X POST http://localhost:8000/api/v1/documents/ \
  -H "X-API-Key: dm_xxxx" \
  -F "title=Test Document" \
  -F "file=@/path/to/your/test.pdf"
# → {"id": "3fa85f64-...", "status": "pending", ...}

# 2. Poll until status=ready (replace with your doc ID)
curl -H "X-API-Key: dm_xxxx" \
  http://localhost:8000/api/v1/documents/3fa85f64-.../
# → {"status": "ready", "chunk_count": 47, ...}

# 3. Semantic search (verify retrieval is working)
curl -X POST http://localhost:8000/api/v1/query/search/ \
  -H "X-API-Key: dm_xxxx" \
  -H "Content-Type: application/json" \
  -d '{"query": "what is this document about?", "document_id": "3fa85f64-...", "k": 3}'

# 4. Streaming Q&A (the main feature)
curl -X POST http://localhost:8000/api/v1/query/ask/ \
  -H "X-API-Key: dm_xxxx" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  --no-buffer \
  -d '{"query": "what is this document about?", "document_id": "3fa85f64-..."}'
# → stream of: data: The document... (tokens) + event: citations + event: done

# 5. Agent analysis (multi-hop reasoning)
curl -X POST http://localhost:8000/api/v1/analysis/ \
  -H "X-API-Key: dm_xxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the key topics and any risks mentioned?",
    "document_ids": ["3fa85f64-..."],
    "workflow_type": "multi_hop"
  }'
# → {"id": "7c9e6679-...", "status": "pending"}

# 6. Poll the analysis job
curl -H "X-API-Key: dm_xxxx" \
  http://localhost:8000/api/v1/analysis/7c9e6679-.../
# → {"status": "complete", "result_data": {"final_answer": "...", ...}}

# 7. Health check (no auth needed)
curl http://localhost:8000/api/v1/health/
# → {"status": "healthy", "checks": {"postgres": "ok", "redis": "ok"}}
```

---

## Switching LLM Providers

**Fully local (no API keys, everything free):**
```bash
OLLAMA_ENABLED=true
OLLAMA_MODEL=qwen2.5:3b
AGENT_LLM_PROVIDER=ollama
RAGAS_JUDGE_PROVIDER=ollama
```
Tradeoff: slower (60–300s per agent job on consumer hardware), lower answer quality.

**OpenAI only:**
```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
AGENT_LLM_PROVIDER=openai
RAGAS_JUDGE_PROVIDER=openai
RAGAS_LLM_MODEL=gpt-4o-mini
OLLAMA_ENABLED=false
```
Tradeoff: API costs, data leaves your machine, but much faster and better quality.

**Full fallback chain (production-like):**
```bash
# Set all providers — system tries OpenAI first, falls back on failure
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
OLLAMA_ENABLED=true
AGENT_LLM_PROVIDER=openai
```
The fallback chain order: OpenAI → Anthropic → Bedrock → Ollama. If OpenAI times out, Anthropic takes over — zero code changes needed.

---

## Useful Commands

```bash
# Run all unit tests (no Docker services needed)
uv run pytest tests/unit/ -v

# Run a specific test file
uv run pytest tests/unit/test_retrieval.py -v

# Run tests matching a keyword
uv run pytest -k "hybrid" -v

# Run the linter
uv run ruff check .

# Auto-fix lint issues
uv run ruff check --fix .

# Run the formatter check
uv run ruff format --check .

# Apply formatter
uv run ruff format .

# Open the Django shell (for debugging, manual queries)
uv run python manage.py shell

# Create a Django superuser (for /admin/)
uv run python manage.py createsuperuser

# Check Django configuration for errors
uv run python manage.py check

# Generate new migrations after model changes
uv run python manage.py makemigrations

# Apply all pending migrations
uv run python manage.py migrate

# Generate a random Django SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

---

## Project Structure

```
DocuMind/
├── core/                    # Django settings, middleware, error handling
│   ├── settings.py          # All settings — reads from .env
│   ├── middleware.py        # RequestID middleware — injects request_id into all logs
│   ├── exceptions.py        # Base DocuMindError with http_status_code
│   ├── error_handler.py     # DRF exception handler — all errors → {"detail": "..."}
│   ├── health.py            # GET /api/v1/health/ — no auth, checks postgres + redis
│   ├── rate_limit.py        # Redis-backed sliding window rate limiter
│   ├── throttles.py         # Per-endpoint DRF throttle classes
│   └── constants.py         # Rate limit values, project-wide constants
│
├── documents/               # Document upload, storage, ingestion lifecycle
│   ├── models.py            # Document, DocumentChunk models
│   ├── views.py             # POST /documents/, GET /documents/{id}/
│   ├── serializers.py       # Upload validation + response shaping
│   ├── tasks.py             # Celery ingestion task (max_retries=0)
│   ├── services.py          # create_document, trigger_ingestion, status transitions
│   └── selectors.py         # get_document_by_id — read-only DB queries
│
├── ingestion/               # Pure Python pipeline — no Django imports
│   ├── pipeline.py          # IngestionPipeline.run() — parse → chunk → embed → BM25
│   ├── parsers.py           # PDF parser (pypdf), extensible via dispatch dict
│   ├── chunkers.py          # HierarchicalChunker — 128-token child, 512-token parent
│   ├── embedders.py         # SentenceTransformerEmbedder (all-MiniLM-L6-v2, 384-dim)
│   └── bm25.py              # BM25Index — build + serialize to Redis
│
├── retrieval/               # Pure Python pipeline — no Django imports
│   ├── pipeline.py          # RetrievalPipeline — orchestrates all 4 stages
│   ├── vector_store.py      # VectorStore — pgvector cosine search
│   ├── bm25.py              # BM25Index deserialization + search
│   ├── hybrid.py            # HybridFusion — RRF (k=60, Cormack 2009)
│   └── reranker.py          # CrossEncoderReranker (ms-marco-MiniLM-L-6-v2)
│
├── generation/              # Pure Python — LLM providers, streaming, prompts
│   ├── llm.py               # LLMProviderPort Protocol + 4 concrete providers + FallbackLLMClient
│   ├── streaming.py         # SSE event builders (token, citations, done, error)
│   └── prompts.py           # All prompt strings, key-based lookup
│
├── query/                   # Django app — search + streaming ask endpoints
│   ├── models.py            # SemanticCacheEntry (VectorField 384-dim, HNSW index)
│   ├── views.py             # POST /query/search/, POST /query/ask/
│   ├── serializers.py       # Request validation, ChunkResult response
│   ├── services.py          # execute_search, execute_ask — compose pipeline + LLM
│   └── semantic_cache.py    # SemanticCache — pgvector similarity lookup + store
│
├── agents/                  # Pure Python — LangGraph state machine
│   ├── graph.py             # build_agent_graph() — all nodes + routing functions
│   ├── executor.py          # AgentExecutor + _get_executor() singleton
│   ├── query_planner.py     # QueryPlanner — classify + decompose via Instructor
│   ├── schemas.py           # Pydantic models: ComplexityClassification, QueryDecomposition
│   ├── tools.py             # RetrievalTool — wraps RetrievalPipeline for agent nodes
│   └── constants.py         # AGENT_RETRIEVAL_K, AGENT_COMPARISON_K, sub-question limits
│
├── analysis/                # Django app — async agent job lifecycle
│   ├── models.py            # AnalysisJob (UUID PK, status, input_data, result_data)
│   ├── views.py             # POST /analysis/, GET /analysis/{id}/
│   ├── serializers.py       # Request validation + job response
│   ├── tasks.py             # Celery analysis task — runs LangGraph state machine
│   └── services.py          # create_analysis_job, mark_job_*, cache_job_result
│
├── authentication/          # Django app — API key auth + permission classes
│   ├── models.py            # APIKey — SHA-256 hash, name, created_at, last_used_at
│   ├── authentication.py    # DRF authentication backend
│   └── management/commands/create_api_key.py  # management command
│
├── evaluation/              # Pure Python — RAGAS evaluation framework
│   ├── harness.py           # EvaluationHarness — runs full pipeline + baseline + compare
│   ├── adapters.py          # FullSystemAdapter + NaiveBaselineAdapter (BM25-only)
│   ├── metrics.py           # RAGASScorer wrapper
│   ├── datasets.py          # QA dataset loading + caching
│   └── reports.py           # JSON + Markdown report generation
│
├── tests/
│   ├── fakes.py             # Shared test doubles (FakeLLMProvider, FakeRetrievalTool, etc.)
│   ├── conftest.py          # Pytest fixtures (sample text, PDF generation)
│   ├── unit/                # 200+ tests, no Docker services needed
│   ├── integration/         # Requires running docker compose services
│   └── evals/               # RAGAS evaluation runner (requires running server + LLM)
│
├── docker-compose.yml       # postgres, redis, flower, ollama, minio
├── pyproject.toml           # Dependencies (uv), ruff config, pytest config
└── .env.example             # Environment variable template
```
