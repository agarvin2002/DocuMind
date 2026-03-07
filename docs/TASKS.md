# DocuMind — Task Tracker

## How to Use This File

This file is updated at the end of every work session.
At the start of a new Claude session, read this file first to know exactly
where we left off and what to do next.

---

## Current Status

**Active Phase:** Phase 1 — Project Foundation
**Phase Status:** NOT STARTED
**Last Updated:** Session 1 (project initialization)
**Last Completed Task:** Created all project documents

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

### Status: TODO

- [ ] **1.1** Install uv (Python package manager)
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

### Status: NOT STARTED (complete Phase 1 first)

- [ ] **2.1** Create src/documind/ingestion/parsers.py
- [ ] **2.2** Create src/documind/ingestion/chunkers.py (hierarchical chunking)
- [ ] **2.3** Create src/documind/ingestion/embedders.py
- [ ] **2.4** Create retrieval/vector_store.py (pgvector interface via Django ORM)
- [ ] **2.5** Create BM25 index manager
- [ ] **2.6** Create src/documind/ingestion/pipeline.py (full orchestration)
- [ ] **2.7** Configure Celery with Redis
- [ ] **2.8** Create Celery ingestion task
- [ ] **2.9** Create POST /documents API route
- [ ] **2.10** Create GET /documents/{id} API route
- [ ] **2.11** Test: upload a real PDF and verify it is indexed

---

## Phase 3 Tasks — Retrieval System

### Status: NOT STARTED

- [ ] **3.1** Implement Qdrant semantic search
- [ ] **3.2** Implement BM25 keyword search
- [ ] **3.3** Implement RRF hybrid fusion
- [ ] **3.4** Implement cross-encoder re-ranker
- [ ] **3.5** Create retrieval pipeline (combines all steps)
- [ ] **3.6** Create scripts/benchmark.py
- [ ] **3.7** Verify hybrid + rerank beats vector-only in benchmark

---

## Phase 4 Tasks — LLM Generation + Streaming

### Status: NOT STARTED

- [ ] **4.1** Create src/documind/generation/llm.py (Claude client)
- [ ] **4.2** Create src/documind/generation/prompts.py
- [ ] **4.3** Create src/documind/generation/schemas.py (Instructor models)
- [ ] **4.4** Create src/documind/generation/streaming.py
- [ ] **4.5** Set up LangSmith tracing
- [ ] **4.6** Create POST /query endpoint (streaming)
- [ ] **4.7** Test: ask a question, get a streaming answer with citations

---

## Phase 5 Tasks — AI Agent Pipeline

### Status: NOT STARTED

- [ ] **5.1** Create agent tools (search, summarize)
- [ ] **5.2** Build LangGraph state machine
- [ ] **5.3** Implement query planner (decomposition)
- [ ] **5.4** Implement multi-hop search executor
- [ ] **5.5** Implement result synthesizer
- [ ] **5.6** Create document comparison workflow
- [ ] **5.7** Create contradiction detection workflow
- [ ] **5.8** Create POST /analysis endpoint
- [ ] **5.9** Test: ask a complex question that requires multi-hop reasoning

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
4. Begin at Phase 1, Task 1.1
