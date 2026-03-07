# DocuMind

AI-native document intelligence system. Upload documents, ask questions, get grounded answers with citations. Built on hybrid retrieval (semantic + keyword), LLM generation, and an agent layer for multi-step reasoning workflows.

---

## Features

- **Document ingestion** — Upload PDFs; parsed, chunked, and embedded asynchronously via Celery
- **Hybrid search** — Combines pgvector semantic search with BM25 keyword search, re-ranked for precision
- **Grounded Q&A** — Answers cite the exact source chunk; no hallucinations
- **Streaming responses** — Token-by-token streaming with inline citations
- **Agent workflows** — Multi-hop reasoning, document comparison, contradiction detection
- **REST API** — Versioned at `/api/v1/`, auto-documented at `/api/docs/`

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | Python 3.12, Django 4.2, Django REST Framework |
| Database | PostgreSQL + pgvector |
| Task queue | Celery + Redis |
| LLM | OpenAI GPT-4o (primary), Anthropic Claude (fallback) |
| Structured output | Instructor |
| Agent framework | LangChain + LangGraph |
| Observability | LangSmith, structured JSON logging |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`, 384d) |
| Keyword search | rank-bm25 |
| File storage | MinIO (local) → AWS S3 (production) |
| Package manager | uv |
| Infrastructure | Docker Compose |

---

## Quick Start

### Prerequisites

- [uv](https://docs.astral.sh/uv/) — Python package manager
- [Docker Desktop](https://www.docker.com/products/docker-desktop)

### Setup

```bash
# Install dependencies
uv sync

# Copy environment config
cp .env.example .env
# Fill in your API keys in .env

# Start infrastructure (PostgreSQL + Redis + MinIO)
docker compose up -d

# Run migrations
uv run python manage.py migrate

# Start the dev server
uv run python manage.py runserver
```

### Start the task worker (separate terminal)

```bash
uv run celery -A core worker --loglevel=info
```

### Verify

```bash
curl http://localhost:8000/api/v1/health/
# {"status": "healthy", "checks": {"postgres": "ok", "redis": "ok"}, "version": "0.1.0"}
```

API docs: [http://localhost:8000/api/docs/](http://localhost:8000/api/docs/)

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/health/` | Health check |
| `POST` | `/api/v1/documents/` | Upload a document |
| `GET` | `/api/v1/documents/` | List all documents |
| `GET` | `/api/v1/documents/{id}/` | Get document status |
| `DELETE` | `/api/v1/documents/{id}/` | Delete a document |
| `POST` | `/api/v1/query/` | Ask a question |
| `POST` | `/api/v1/analysis/compare/` | Compare two documents |
| `POST` | `/api/v1/analysis/contradictions/` | Find contradictions across corpus |

---

## Project Structure

```
DocuMind/
├── core/               # Django settings, URLs, middleware, Celery app
├── documents/          # Document model, upload API, ingestion tasks
├── query/              # Q&A API, retrieval orchestration
├── analysis/           # Agent workflows (comparison, contradiction detection)
├── ingestion/          # Pure Python: PDF parsing, chunking, embedding
├── retrieval/          # Pure Python: vector store, BM25, hybrid search, reranker
├── generation/         # Pure Python: LLM client, prompts, streaming, schemas
├── agents/             # Pure Python: LangGraph agent definitions
├── evaluation/         # Retrieval and generation benchmarks
├── tests/
│   ├── unit/           # No Docker required
│   └── integration/    # Requires running services
├── docs/               # Architecture, roadmap, dev commands
└── docker-compose.yml
```

---

## Running Tests

```bash
# Unit tests (no Docker required)
uv run pytest tests/unit/

# All tests (requires Docker services running)
uv run pytest

# Linting
uv run ruff check .
```

---

## Environment Variables

Copy `.env.example` to `.env` and configure:

```env
SECRET_KEY=...
DATABASE_URL=postgresql://documind:documind@localhost:5432/documind
REDIS_URL=redis://localhost:6379
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_STORAGE_BUCKET_NAME=...
AWS_S3_ENDPOINT_URL=http://localhost:9000   # remove for production AWS S3
LOG_FORMAT=verbose                          # set to "json" in production
```

