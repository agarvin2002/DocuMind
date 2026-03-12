# DocuMind — Task Tracker

## How to Use This File

This file is updated at the end of every work session.
At the start of a new Claude session, read this file first to know exactly
where we left off and what to do next.

---

## Current Status

**Active Phase:** Phase 4 — LLM Generation + Streaming
**Phase Status:** NOT STARTED
**Last Updated:** Session — Phase 3 complete
**Last Completed Task:** Phase 3 — Retrieval System (all tasks complete, 46+ tests green)

---

## Session Log

### Phase 3 — Retrieval System (COMPLETE)

**What we built:**
- `retrieval/schemas.py` — `ChunkSearchResult` dataclass (universal result object)
- `retrieval/protocols.py` — 4 structural Protocol ports (QueryEmbedderPort, VectorSearchPort, KeywordSearchPort, RerankerPort)
- `retrieval/bm25.py` — added `search()` method; fixed BM25Okapi epsilon-floor edge case
- `retrieval/vector_store.py` — `VectorStore` adapter with logging
- `retrieval/hybrid.py` — `HybridFusion` class implementing RRF (Reciprocal Rank Fusion, k=60)
- `retrieval/reranker.py` — `CrossEncoderReranker` using `cross-encoder/ms-marco-MiniLM-L-6-v2`
- `retrieval/pipeline.py` — `RetrievalPipeline` orchestrator (embed → vector → BM25 → fuse → rerank → top-k)
- `ingestion/embedders.py` — added `embed_single()` method for query embedding at search time
- `ingestion/protocols.py` — added `embed_single` to `EmbedderProtocol`
- `documents/selectors.py` — `vector_search_chunks()`, `keyword_search_chunks()`, `_get_bm25_index_or_rebuild()`
- `documents/services.py` — `save_bm25_index()` (Redis persistence, 7-day TTL)
- `documents/tasks.py` — wired BM25 persistence after ingestion (Phase 2 gap closed)
- `query/serializers.py` — `SearchRequestSerializer`, `ChunkResultSerializer`, `SearchResponseSerializer`
- `query/services.py` — `execute_search()` composition root
- `query/views.py` — `SearchView` (POST /api/v1/query/search/)
- `query/urls.py` — URL registration
- `tests/unit/test_retrieval.py` — 18 unit tests (no Docker required)
- `tests/integration/test_search.py` — 7 integration tests (require Docker)
- `docs/PHASE3_PLAN.md` — staff engineer implementation plan
- `docs/PHASE3_TEACHING.md` — comprehensive 14-stop teaching guide

**Verification status:**
- [x] `uv run ruff check .` — clean (0 errors)
- [x] `uv run pytest tests/unit/ -v` — all unit tests pass (no Docker needed)
- [ ] `uv run pytest tests/integration/ -v` — NOT YET RUN (requires Docker)
- [ ] `uv run python manage.py check` — NOT YET RUN this session
- [ ] Feature branch + PR — NOT YET CREATED

**Known tech debt (from Phase 2, still open):**
- `documents/admin.py` — needs `raw_id_fields = ["document"]` on `DocumentChunkAdmin`

---

### Phase 2 — Document Ingestion Pipeline (COMPLETE)

**What we built:**
- `ingestion/parsers.py` — PDF parser using pypdf
- `ingestion/chunkers.py` — hierarchical chunker (child + parent chunks)
- `ingestion/embedders.py` — sentence-transformers embedder
- `ingestion/pipeline.py` — full ingestion orchestrator
- `documents/models.py` — Document + DocumentChunk with pgvector `VectorField`
- `documents/serializers.py`, `views.py`, `services.py`, `selectors.py`, `tasks.py`
- POST /api/v1/documents/ — upload endpoint
- GET /api/v1/documents/{id}/ — status + detail endpoint
- Celery task: PDF → parse → chunk → embed → store (status: pending → processing → ready/failed)
- BM25 index built during ingestion (persisted to Redis in Phase 3 patch)
- HNSW index migration (0002) for fast pgvector search

**End-to-end verified:** PDF upload → `pending` → `processing` → `ready`, `chunk_count > 0`, embeddings in pgvector.

---

### Phase 1 — Project Foundation (COMPLETE)

**What we built:**
- uv project setup, pyproject.toml with all dependencies
- Docker Compose (PostgreSQL + pgvector + Redis + MinIO + Flower)
- Django settings (core/settings.py) with 12-Factor config via environs
- Health check endpoint: GET /api/v1/health/
- RequestID middleware (core/middleware.py)
- Dual-format logging (verbose local / JSON production)
- Security headers, CORS, ruff + pytest configured in pyproject.toml
- GitHub Actions CI pipeline + PR template

---

## Phase 3 Tasks — Retrieval System

### Status: COMPLETE ✓

- [x] **3.1** `retrieval/schemas.py` — ChunkSearchResult dataclass
- [x] **3.2** `retrieval/protocols.py` — Port protocols (structural typing)
- [x] **3.3** `retrieval/bm25.py` — search() method
- [x] **3.4** `retrieval/vector_store.py` — VectorStore adapter
- [x] **3.5** `retrieval/hybrid.py` — HybridFusion (RRF)
- [x] **3.6** `retrieval/reranker.py` — CrossEncoderReranker
- [x] **3.7** `retrieval/pipeline.py` — RetrievalPipeline orchestrator
- [x] **3.8** `documents/selectors.py` — vector_search_chunks, keyword_search_chunks
- [x] **3.9** `documents/services.py` — save_bm25_index (Redis)
- [x] **3.10** `query/serializers.py` — request/response validation
- [x] **3.11** `query/services.py` — execute_search() composition root
- [x] **3.12** `query/views.py` + `query/urls.py` — POST /api/v1/query/search/
- [x] **3.13** Unit tests (18 tests, no Docker)
- [x] **3.14** Integration tests written (7 tests, Docker required)
- [ ] **3.15** Run integration tests with Docker
- [ ] **3.16** Create feature/retrieval-system branch + PR

---

## Phase 4 Tasks — LLM Generation + Streaming

### Status: NOT STARTED (complete Phase 3 integration tests + PR first)

**What Phase 4 builds:**
The query now returns matching text chunks. Phase 4 takes those chunks and uses
an LLM (GPT-4o) to generate a natural language answer with citations.
It also adds streaming so the answer appears word-by-word (like ChatGPT).

- [ ] **4.1** `generation/schemas.py` — Pydantic models for LLM inputs/outputs
- [ ] **4.2** `generation/prompts.py` — system prompt + user prompt templates
- [ ] **4.3** `generation/llm.py` — OpenAI client with streaming + Instructor structured output
- [ ] **4.4** `generation/citations.py` — citation extraction and formatting
- [ ] **4.5** `generation/pipeline.py` — generation orchestrator (chunks → answer + citations)
- [ ] **4.6** `query/services.py` — extend execute_search() to also generate answer
- [ ] **4.7** `query/views.py` — add POST /api/v1/query/answer/ (streaming SSE)
- [ ] **4.8** LangSmith tracing setup (trace every LLM call)
- [ ] **4.9** Unit tests for generation layer
- [ ] **4.10** Integration test: POST question → get answer with citations

---

## Phase 5 Tasks — AI Agent Pipeline

### Status: NOT STARTED

- [ ] **5.1** `agents/tools.py` — search tool, summarize tool
- [ ] **5.2** `agents/state.py` — LangGraph state schema
- [ ] **5.3** `agents/planner.py` — query decomposition node
- [ ] **5.4** `agents/executor.py` — multi-hop search executor node
- [ ] **5.5** `agents/synthesizer.py` — result synthesis node
- [ ] **5.6** `agents/graph.py` — LangGraph state machine wiring
- [ ] **5.7** `analysis/` app — comparison + contradiction detection workflows
- [ ] **5.8** POST /api/v1/analysis/compare/ + /contradict/ endpoints
- [ ] **5.9** Integration test: multi-hop question answered correctly

---

## Phase 6 Tasks — Evaluation Framework

### Status: NOT STARTED

- [ ] **6.1** Create 50 ground-truth Q&A pairs (evaluation dataset)
- [ ] **6.2** `evaluation/dataset.py` — dataset loader
- [ ] **6.3** `evaluation/metrics.py` — RAGAS metrics (faithfulness, context precision, answer relevance)
- [ ] **6.4** `evaluation/harness.py` — automated eval runner
- [ ] **6.5** Baseline comparison (naive vector-only vs hybrid+rerank)
- [ ] **6.6** Generate evaluation report

---

## Phase 7 Tasks — Production Readiness

### Status: NOT STARTED

- [ ] **7.1** API key authentication (DRF token auth or JWT)
- [ ] **7.2** Rate limiting (django-ratelimit or DRF throttling)
- [ ] **7.3** Semantic caching (cache LLM answers for repeated questions)
- [ ] **7.4** Final security audit (no secrets in code or git history)
- [ ] **7.5** README with demo, architecture diagram, benchmarks
- [ ] **7.6** Production Dockerfile + deployment notes

---

## Decisions Made

| Decision | Choice | Reason |
|----------|--------|--------|
| Language | Python 3.12 | AI industry standard |
| Package manager | uv | Modern, fast, replacing pip |
| Web framework | Django 4.2 + DRF | Most Python backend jobs require Django |
| ORM | Django ORM + migrations | Built into Django, no extra tools needed |
| Relational DB | PostgreSQL | Production standard |
| Vector search | pgvector (PostgreSQL extension) | No extra service — uses existing PostgreSQL |
| Cache/Queue | Redis | Dual purpose: cache + Celery broker |
| Primary LLM | OpenAI GPT-4o | Most job postings mention OpenAI |
| Fallback LLM | Anthropic Claude Sonnet | Best reasoning, important to know both |
| Structured output | Instructor | Validated Pydantic models from LLM |
| Agent framework | LangChain + LangGraph | LangChain most mentioned in job postings |
| Observability | LangSmith | Full LLM call tracing |
| Embedding model | sentence-transformers | Local, free, production quality |
| Hybrid search | pgvector + BM25 + RRF | Semantic + keyword, fused via Reciprocal Rank Fusion |
| Reranker | cross-encoder/ms-marco-MiniLM-L-6-v2 | Accurate cross-attention scoring, fast enough for top-k |
| BM25 persistence | Redis (key: documind:bm25:{id}, TTL 7d) | Avoids rebuilding from DB on every search |

---

## Blockers

None currently.

---

## Next Session Starting Point

**Start here when opening a new Claude session:**

1. Read `docs/PROJECT_CONTEXT.md`
2. Read this file (`docs/TASKS.md`) — current phase is **Phase 4**
3. Read `docs/DEV_COMMANDS.md` for commands
4. Before starting Phase 4: run integration tests for Phase 3
   ```bash
   docker compose up -d
   uv run python manage.py migrate
   uv run pytest tests/integration/test_search.py -v
   ```
5. After integration tests pass: create `feature/retrieval-system` branch and PR
6. Then begin Phase 4 (Generation layer)
