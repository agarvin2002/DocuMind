# DocuMind — Task Tracker

## How to Use This File

This file is updated at the end of every work session.
At the start of a new Claude session, read this file first to know exactly
where we left off and what to do next.

---

## Current Status

**Active Phase:** Phase 5 — AI Agent Pipeline
**Phase Status:** COMPLETE — branch `feature/agent-pipeline` ready to merge to `main`
**Last Updated:** 2026-03-20
**Last Completed Task:** Phase 5 fully implemented, engineering review done, 6 high-severity issues fixed, smoke tests passing for both Phase 4 and Phase 5

---

## Session Log

### Session 2 — Stack Refinement
**What we did:**
- Replaced Qdrant with pgvector (PostgreSQL extension)
- Reason: pgvector uses existing PostgreSQL — no extra container, simpler stack,
  more common in Django job postings
- Updated all 5 project documents to reflect the change

---

### Session 1 — Project Initialization
**What we did:**
- Defined the project: DocuMind, an AI document intelligence system
- Chose the full tech stack with explanations
- Created all 6 project documents
- Revised tech stack based on job market feedback:
  - FastAPI → Django 4.2 + Django REST Framework (more jobs)
  - SQLAlchemy + Alembic → Django ORM + Django migrations (simpler, built-in)
  - Claude only → OpenAI (primary) + Claude (fallback) (more job postings mention OpenAI)
  - LangGraph only → LangChain + LangGraph (LangChain most mentioned in postings)
- Updated all documents to reflect the revised stack

**What we did NOT do yet:**
- Write any code
- Set up the Python project
- Configure Docker

---

## Phase 1 Tasks — Project Foundation

### Status: COMPLETE ✓

- [x] **1.1** Install uv (Python package manager)
- [ ] **1.2** Initialize Python project with uv (`uv init`)
- [ ] **1.3** Create pyproject.toml with all dependencies
- [ ] **1.4** Create folder structure (src/documind/ and all subdirectories)
- [ ] **1.5** Create docker-compose.yml (Postgres with pgvector + Redis)
- [ ] **1.6** Create .env.example with all required variables documented
- [ ] **1.7** Create .gitignore
- [ ] **1.8** Create core/settings.py (Django settings loaded from .env)
- [ ] **1.9** Create core/urls.py (root URL router)
- [ ] **1.10** Create documents/models.py (Document and Job tables)
- [ ] **1.11** Run first Django migration: `python manage.py makemigrations && migrate`
- [ ] **1.12** Create core/urls.py with /api/health/ endpoint
- [ ] **1.13** Create Django superuser for admin panel
- [ ] **1.14** Verify: `docker compose up -d` starts all services
- [ ] **1.15** Verify: `python manage.py runserver` starts without errors
- [ ] **1.16** Verify: GET /api/health/ returns 200
- [ ] **1.17** Verify: Django admin panel loads at /admin/
- [ ] **1.18** Verify: pgvector extension active in PostgreSQL
- [ ] **1.19** Verify: Can connect to both services (Postgres + pgvector, Redis)

---

## Phase 2 Tasks — Document Ingestion Pipeline

### Status: COMPLETE ✓

- [x] **2.1** Create ingestion/parsers.py
- [x] **2.2** Create ingestion/chunkers.py (hierarchical chunking)
- [x] **2.3** Create ingestion/embedders.py
- [x] **2.4** Create retrieval/vector_store.py (pgvector interface via Django ORM)
- [x] **2.5** Create BM25 index manager (retrieval/bm25.py)
- [x] **2.6** Create ingestion/pipeline.py (full orchestration)
- [x] **2.7** Configure Celery with Redis
- [x] **2.8** Create Celery ingestion task (documents/tasks.py)
- [x] **2.9** Create POST /documents API route
- [x] **2.10** Create GET /documents/{id} API route
- [x] **2.11** Unit tests for all ingestion components

---

## Phase 3 Tasks — Retrieval System

### Status: COMPLETE ✓

- [x] **3.1** retrieval/schemas.py — ChunkSearchResult dataclass
- [x] **3.2** retrieval/protocols.py — QueryEmbedderPort, VectorSearchPort, KeywordSearchPort, RerankerPort
- [x] **3.3** ingestion/embedders.py — added embed_single()
- [x] **3.4** retrieval/bm25.py — added BM25Index.search()
- [x] **3.5** documents/selectors.py — vector_search_chunks, keyword_search_chunks, _get_bm25_index_or_rebuild
- [x] **3.6** documents/services.py — save_bm25_index (Redis, 7-day TTL)
- [x] **3.7** documents/tasks.py — call save_bm25_index after ingestion
- [x] **3.8** retrieval/vector_store.py — VectorStore wrapping VectorSearchPort
- [x] **3.9** retrieval/hybrid.py — HybridFusion with RRF scoring
- [x] **3.10** retrieval/reranker.py — CrossEncoderReranker (lazy model load)
- [x] **3.11** retrieval/pipeline.py — RetrievalPipeline (embed → vector → keyword → fuse → rerank)
- [x] **3.12** query/serializers.py — SearchRequestSerializer, ChunkResultSerializer
- [x] **3.13** query/services.py — execute_search composition root, NoRelevantChunksError
- [x] **3.14** query/views.py + query/urls.py — POST /api/v1/query/search/ endpoint
- [x] **3.15** tests/unit/test_retrieval.py — 25 unit tests for BM25, HybridFusion, RetrievalPipeline

---

## Phase 4 Tasks — LLM Generation + Streaming

### Status: COMPLETE ✓

- [x] **4.1** generation/schemas.py — Citation + GeneratedAnswer Pydantic models
- [x] **4.2** generation/prompts.py — versioned system prompt, context window guard
- [x] **4.3** generation/streaming.py — SSE wire format helpers
- [x] **4.4** generation/llm.py — OpenAI, Anthropic, Bedrock, Ollama providers + FallbackLLMClient
- [x] **4.5** core/settings.py + .env.example — LLM settings block (all 4 providers)
- [x] **4.6** query/services.py — execute_ask(), _get_provider_registry(), _resolve_provider()
- [x] **4.7** query/serializers.py — AskRequestSerializer (query, document_id, k, model)
- [x] **4.8** query/views.py + query/urls.py — AskView, POST /api/v1/query/ask/ (SSE streaming)
- [x] **4.9** docker-compose.yml — Ollama service + ollama_data volume
- [x] **4.10** tests/unit/test_generation.py — 37 unit tests (95 total passing)

---

## Phase 5 Tasks — AI Agent Pipeline

### Status: COMPLETE ✓ (branch: feature/agent-pipeline — open PR to merge to main)

- [x] **5.1** Create agent tools — RetrievalTool, GenerationTool (agents/tools.py)
- [x] **5.2** Build LangGraph state machine — 10 nodes, 4 routing functions (agents/graph.py)
- [x] **5.3** Implement query planner — classify() + decompose() with Redis cache (agents/query_planner.py)
- [x] **5.4** Implement multi-hop search executor — RetrieveForSubquestion + GenerateSubAnswers nodes
- [x] **5.5** Implement result synthesizer — Synthesize node (agents/graph.py)
- [x] **5.6** Create document comparison workflow — ComparisonRetrieve + ComparisonGenerate nodes
- [x] **5.7** Create contradiction detection workflow — ContradictionDetect node
- [x] **5.8** Create POST /analysis/ + GET /analysis/{id}/ endpoints (analysis/views.py)
- [x] **5.9** Smoke tests passing — both Phase 4 streaming and Phase 5 async jobs produce real answers
- [x] **5.10** Engineering review — 13 findings, 6 HIGH fixed (F-01 to F-06 + F-10)
- [x] **5.11** 127 Phase 5 unit tests passing (241 total)
- [x] **5.12** OLLAMA_KEEP_ALIVE=-1 — permanent fix for cold-start timeouts

### Phase 5 follow-up (track in feature/phase5-polish PR)

- [ ] **5.P1** F-07: Wire get_cached_result() into AnalysisJobDetailView — Redis fast path never called
- [ ] **5.P2** F-08: Citations always return [] — extract from ChunkSearchResult in all terminal nodes
- [ ] **5.P3** F-09: Remove dead code get_system_prompt() + _PROMPTS from generation/prompts.py
- [ ] **5.P4** F-11: Move local uuid imports to module level in agents/graph.py
- [ ] **5.P5** F-12: Add E2E graph tests for comparison and contradiction workflows
- [ ] **5.P6** F-13: Fix StructuredLLMPort.complete() return type from object to T in agents/protocols.py

---

## Phase 6 Tasks — Evaluation Framework

### Status: NOT STARTED

- [ ] **6.1** Create 50 ground-truth Q&A pairs
- [ ] **6.2** Create evaluation dataset loader
- [ ] **6.3** Implement RAGAS metrics
- [ ] **6.4** Build eval harness (runs all metrics automatically)
- [ ] **6.5** Create baseline (naive vector-only RAG) for comparison
- [ ] **6.6** Generate evaluation report
- [ ] **6.7** Document results in README

---

## Phase 7 Tasks — Production Readiness

### Status: NOT STARTED

- [ ] **7.1** Implement API key authentication
- [ ] **7.2** Implement rate limiting
- [ ] **7.3** Implement semantic caching
- [ ] **7.4** Add structured error handling to all routes
- [ ] **7.5** Write README with demo, architecture diagram, benchmarks
- [ ] **7.6** Final security audit (no secrets in code or git history)

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

---

## Blockers

None currently.

---

## Next Session Starting Point

**Start here when opening a new Claude session:**

1. Read PROJECT_CONTEXT.md first
2. Read this file (TASKS.md) to see current phase and next task
3. Read DEV_COMMANDS.md to know how to start the project
4. Begin Phase 5 — AI Agent Pipeline

**Current branch:** feature/agent-pipeline
**Pre-push checklist:** ruff clean ✓ | 241 unit tests green ✓ | manage.py check clean ✓ | smoke tests passing ✓
**Next:** Open PR feature/agent-pipeline → main, then start feature/phase5-polish for follow-up items (5.P1–5.P6), then begin Phase 6 — Evaluation Framework
