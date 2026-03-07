# DocuMind — Project Context

## Purpose of This File

This file exists to give a new Claude session full context about the project
in under 5 minutes. Read this file at the start of every session before doing
anything else. Then read TASKS.md to find the current task.

---

## What Is This Project?

DocuMind is an AI-native document intelligence system — a portfolio project
built to demonstrate real-world AI engineering skills to companies like
Cursor, Glean, Perplexity, and Harvey.

Users upload documents (PDFs, text files, web pages) and can:
- Ask complex questions and get answers with citations
- Run automated analysis workflows (comparison, contradiction detection)
- Access everything via a REST API

Full product details: see PRODUCT_OVERVIEW.md

---

## Who Is Building This?

A developer learning programming from scratch. They are new to all
technologies in this stack. Every concept must be explained simply and
clearly before implementation. Never assume prior knowledge.

---

## How to Behave in Every Session

1. Read PROJECT_CONTEXT.md (this file) first
2. Read TASKS.md to know current phase and next task
3. Read DEV_COMMANDS.md to know how to start/stop services
4. Follow the 6-step teaching workflow for every task:
   - Step 1: Explain what we are building
   - Step 2: Explain why we are building it
   - Step 3: Explain the concept in beginner-friendly terms
   - Step 4: Show the architecture or design decision
   - Step 5: Provide implementation steps
   - Step 6: Write the code
5. Update TASKS.md at the end of every session
6. Never skip steps, never assume knowledge

---

## Architecture Summary

```
Client → Django + DRF → Query Engine → Hybrid Retrieval → OpenAI/Claude → Stream
                      → Agent Pipeline (LangChain + LangGraph) → Multi-hop → Synthesize
                      → Ingestion Pipeline (Celery) → Parse → Chunk → Embed → pgvector (PostgreSQL)
```

Full architecture: see ARCHITECTURE.md

---

## Tech Stack (Quick Reference)

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Language | Python 3.12 | Everything |
| Package manager | uv | Install libraries |
| Web framework | Django 4.2 | HTTP API, ORM, admin, auth |
| REST API layer | Django REST Framework (DRF) | Serializers, API views, permissions |
| Relational DB | PostgreSQL | Metadata, jobs |
| ORM + Migrations | Django ORM + Django migrations | DB models and schema changes |
| Vector search | pgvector (PostgreSQL extension) | Embeddings stored in PostgreSQL |
| Cache + Queue | Redis | Caching + Celery broker |
| Background tasks | Celery | Async document processing |
| Primary LLM | OpenAI GPT-4o + GPT-4o-mini | Answer generation (most job postings) |
| Fallback LLM | Anthropic Claude Sonnet | Complex reasoning fallback |
| Structured outputs | Instructor | Validated Pydantic from LLM |
| Embeddings | sentence-transformers | Text → vectors |
| Keyword search | rank-bm25 | BM25 exact matching |
| Agent framework | LangChain + LangGraph | Chains, retrievers, agent state machine |
| LLM observability | LangSmith | Tracing every LLM call |
| Containers | Docker + Docker Compose | Local infrastructure |

---

## Folder Structure (Quick Reference)

```
documind/
├── manage.py          # Django CLI — run all Django commands through this
├── core/              # Django settings, root URLs, wsgi/asgi
├── documents/         # Django app: upload, models, migrations, Celery tasks
├── query/             # Django app: Q&A endpoint
├── analysis/          # Django app: agent workflow endpoints
├── ingestion/         # Core module: parse → chunk → embed → store
├── retrieval/         # Core module: vector search + BM25 + hybrid + rerank
├── generation/        # Core module: LLM calls + prompts + streaming
├── agents/            # Core module: LangGraph agent + tools + query planner
└── evaluation/        # Core module: RAGAS metrics + eval harness
```

Full structure: see ARCHITECTURE.md

---

## Development Phases (Quick Reference)

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Foundation: Docker, DB, config, health API | NOT STARTED |
| 2 | Ingestion: PDF parsing, chunking, embedding | NOT STARTED |
| 3 | Retrieval: Hybrid search, reranking | NOT STARTED |
| 4 | Generation: LLM, streaming, citations | NOT STARTED |
| 5 | Agents: LangGraph, multi-hop, comparison | NOT STARTED |
| 6 | Evaluation: RAGAS, benchmarks, reports | NOT STARTED |
| 7 | Production: Auth, caching, docs, polish | NOT STARTED |

Full roadmap: see ROADMAP.md
Current tasks: see TASKS.md

---

## Critical Rules for This Project

### Never Do These
- Do not write code before explaining what it does and why
- Do not skip phases — complete Phase N before starting Phase N+1
- Do not commit the .env file (it contains secrets)
- Do not hardcode API keys anywhere in code
- Do not use pip directly — use uv for all package management
- Do not start the server with a command not in DEV_COMMANDS.md

### Always Do These
- Explain every concept before implementing it
- Check TASKS.md at the start of every session
- Update TASKS.md at the end of every session
- Run existing tests before starting new work
- Use type hints on every function
- Use Pydantic for all data validation

---

## Key Files to Know

| File | Purpose |
|------|---------|
| PRODUCT_OVERVIEW.md | What the product is and why it exists |
| ARCHITECTURE.md | System design, folder structure, tech choices explained |
| ROADMAP.md | All phases with definitions of done |
| TASKS.md | Current tasks, session log, next steps |
| PROJECT_CONTEXT.md | This file — start here every session |
| DEV_COMMANDS.md | Every command to run this project |
| src/documind/config.py | All configuration — look here for settings |
| docker-compose.yml | Infrastructure setup |
| .env.example | Required environment variables |

---

## Environment Variables Required

These must be set in .env before running the project:

```
# Django
SECRET_KEY=                 # Any long random string (Django uses this for security)
DEBUG=True                  # Set to False in production
ALLOWED_HOSTS=localhost,127.0.0.1

# LLM Providers
OPENAI_API_KEY=             # Get from platform.openai.com
ANTHROPIC_API_KEY=          # Get from console.anthropic.com

# LangSmith (LLM observability)
LANGCHAIN_API_KEY=          # Get from smith.langchain.com
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=documind

# Databases (these work with the docker-compose defaults)
DATABASE_URL=postgresql://documind:documind@localhost:5432/documind
REDIS_URL=redis://localhost:6379
# Note: No separate vector database URL needed — pgvector runs inside PostgreSQL
```

---

## How to Start the Project (Summary)

Full commands in DEV_COMMANDS.md. Quick reference:

```bash
# 1. Start all infrastructure
docker compose up -d

# 2. Run database migrations
uv run python manage.py migrate

# 3. Start the Django development server
uv run python manage.py runserver

# 4. Start background worker (separate terminal)
uv run celery -A core worker --loglevel=info

# 5. Open API docs
open http://localhost:8000/api/docs/

# 6. Open Django admin panel
open http://localhost:8000/admin/
```

---

## Current Blockers

None.

---

## Questions / Decisions Pending

None at this time.
