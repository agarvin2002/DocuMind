# Architecture

## System Overview

DocuMind has two primary request paths.

**Ingestion path:** A user uploads a PDF via `POST /api/v1/documents/`. Django saves the file bytes to MinIO (an S3-compatible object store), creates a `Document` row with `status=PENDING`, and immediately dispatches a Celery task. The Celery worker picks up the task, opens the file from storage, passes it through the `IngestionPipeline` (pure Python — no Django), and persists the result: `DocumentChunk` rows with 384-dim vector embeddings stored in PostgreSQL via pgvector, and a serialized BM25 keyword index stored in Redis. On success, the document transitions to `status=READY`. On failure (parse error, timeout, corrupt file), it transitions to `status=FAILED` with an error message.

**Query path:** A user sends `POST /api/v1/query/ask/`. Before any expensive work, the `SemanticCache` checks PostgreSQL for a semantically similar previous question (cosine distance ≤ 0.08). On a cache hit, the stored answer is streamed directly as SSE events. On a miss, the `RetrievalPipeline` embeds the query, runs vector search and BM25 search in parallel, fuses the results with Reciprocal Rank Fusion, and re-ranks with a cross-encoder. The top chunks are passed to the `FallbackLLMClient`, which streams tokens from whichever LLM provider is available (OpenAI → Anthropic → Bedrock → Ollama). Citations are extracted from `[1]`, `[2]` markers after streaming completes, and the full answer is stored in the semantic cache.

**Agent path:** `POST /api/v1/analysis/` creates an `AnalysisJob` record and returns 202 Accepted. A Celery task runs the LangGraph state machine asynchronously — classifying the query, routing through one of four workflow types, running retrieval one or more times, and producing a structured result. The job is polled via `GET /api/v1/analysis/{id}/`.

## Module Boundaries

This is the most important architectural decision in the codebase.

The five core logic modules — `ingestion/`, `retrieval/`, `generation/`, `agents/`, `evaluation/` — contain **zero Django imports**. They are pure Python transformation layers that accept plain Python objects and return plain Python objects. They know nothing about HTTP, databases, or file storage.

The Django layer owns all side effects:
- `documents/tasks.py` opens files from S3, calls `IngestionPipeline.run()`, and persists results to PostgreSQL + Redis
- `analysis/tasks.py` calls `AgentExecutor.run()` and writes the result back to the `AnalysisJob` record
- `query/services.py` is the composition root that wires together `retrieval/`, `generation/`, `documents/` ORM queries, and `query/semantic_cache.py`

Why this matters: the entire pipeline layer can be tested without Docker, without a database, and without mock-patching module globals. Pass a fake embedder → `IngestionPipeline` produces real output. Pass a fake retrieval tool → the LangGraph graph routes correctly. This is what makes 244 unit tests possible without any external services.

```
Django Layer (side effects allowed)          Pure Python Layer (no Django)
─────────────────────────────────────        ──────────────────────────────
documents/tasks.py          ─────────────>   ingestion/pipeline.py
analysis/tasks.py           ─────────────>   agents/graph.py
query/services.py           ─────────────>   retrieval/pipeline.py
                                             generation/llm.py
                                             evaluation/harness.py
```

## Django App Structure

| App | Single Responsibility |
|-----|-----------------------|
| `documents` | File upload, `Document` + `DocumentChunk` models, chunk persistence |
| `query` | Semantic search, streaming ask, `SemanticCacheEntry` model |
| `analysis` | `AnalysisJob` model, async agent job lifecycle, result polling |
| `authentication` | API key model + auth, per-endpoint rate limiting |
| `core` | Settings, `RequestIDMiddleware`, health check, global error handler |

## Dependency Injection via Structural Protocols

Every pipeline module defines a `Protocol` class describing the interface it needs. Any class whose methods match the protocol signature satisfies it — no inheritance required.

```python
# ingestion/protocols.py
from typing import Protocol

class EmbedderProtocol(Protocol):
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
    def embed_single(self, text: str) -> list[float]: ...

# Production: SentenceTransformerEmbedder satisfies EmbedderProtocol
# Tests:      FakeEmbedder satisfies EmbedderProtocol — no import needed
```

The protocols used throughout the codebase:

| Protocol | Defined In | Satisfied By (prod) | Satisfied By (tests) |
|----------|------------|---------------------|----------------------|
| `ChunkerProtocol` | `ingestion/protocols.py` | `HierarchicalChunker` | `FakeChunker` |
| `EmbedderProtocol` | `ingestion/protocols.py` | `SentenceTransformerEmbedder` | `FakeEmbedder` |
| `LLMProviderPort` | `generation/llm.py` | `OpenAIProvider`, `FallbackLLMClient` | `FakeLLMProvider` |
| `VectorSearchPort` | `retrieval/protocols.py` | `vector_search_chunks` (DB query) | in-memory fake |
| `RetrievalToolPort` | `agents/protocols.py` | `RetrievalTool` | `FakeRetrievalTool` |
| `SemanticCachePort` | `query/protocols.py` | `SemanticCache` | `FakeSemanticCache` |

This is what makes the test suite refactoring-safe: when you rename a method, you update the fake, and all tests still pass because they never reached into implementation internals.

## Data Models

### Document

`Document` represents one uploaded file. Status lifecycle:

```
PENDING → PROCESSING → READY
                     → FAILED
```

Key fields: `id` (UUID PK), `title`, `file` (S3 path), `status` (db_index), `chunk_count` (updated on success), `error_message` (set on failure). File bytes live in MinIO/S3 — only the storage path is in the database.

### DocumentChunk

One text chunk extracted from a `Document`. There are typically 20–200 chunks per document depending on length.

Key fields: `id` (UUID PK), `document` (FK, CASCADE), `chunk_index`, `child_text` (~128 tokens, indexed for retrieval), `parent_text` (~512 tokens, sent to the LLM), `embedding` (`VectorField(dimensions=384)`), `page_number`. Unique constraint on `(document, chunk_index)`.

The child/parent split is the retrieval design decision: the vector index is built on `child_text` (precise, narrow window) but the LLM receives `parent_text` (wider context). See [docs/ingestion.md](ingestion.md) for full details.

### SemanticCacheEntry

One cached question–answer pair for a specific document.

Key fields: `id` (UUID PK), `document` (FK to Document, CASCADE delete), `query_text` (for debugging only), `embedding` (`VectorField(dimensions=384)`), `answer_json` (JSONField: `{answer, citations}`), `created_at`. The HNSW index on `embedding` was added in migration `0002_add_hnsw_index.py` with `atomic=False` (required for `CREATE INDEX CONCURRENTLY` — a regular migration would lock the table). CASCADE delete means removing a document automatically purges all its cache entries.

### AnalysisJob

One async agent pipeline execution.

Key fields: `id` (UUID PK), `workflow_type` (MULTI_HOP / COMPARISON / CONTRADICTION / SIMPLE, db_index), `status` (PENDING → RUNNING → COMPLETE / FAILED, db_index), `input_data` (JSONField: question + document_ids), `result_data` (JSONField, null until complete), `error_message`, `started_at`, `completed_at`. Composite index on `(status, workflow_type)`.

## Request ID Propagation

Every HTTP request gets a unique 12-character hex ID, generated by `RequestIDMiddleware`:

```python
request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
```

The ID is stored in thread-local storage (`threading.local()`). A `RequestIDFilter` injects it into every log record automatically — no manual passing between functions. The response includes `X-Request-ID: <id>` for client-side correlation (useful for support tickets: "give me the request ID from your browser network tab").

In Celery tasks, which run outside an HTTP request, the filter falls back to `"-"` so the field is always present in JSON log output.

## Error Handling Contract

Three layers, each with a distinct pattern:

**HTTP layer:** Custom exception hierarchy with `http_status_code` on each exception class (`DocuMindError` → `NotFoundError` (404), `ValidationError` (400), `ProcessingError` (422), `StorageError` (503), `LLMError` (502)). A central `documind_exception_handler` in DRF catches all exceptions and converts them to `{"detail": "<message>"}` JSON with the correct status code. No view function handles exceptions directly.

**Agent layer:** Nodes in the LangGraph state machine never raise exceptions to the graph engine. On any failure, a node catches the exception, sets `state["error"] = str(exc)`, and returns the state dict. Every routing function checks `if state.get("error"):` before deciding the next node — if set, it routes to `error_node`. The `error_node` formats a user-facing message and provides empty `citations`, ensuring the result dict is always structurally complete. This prevents jobs from getting stuck in `RUNNING` status.

**Infrastructure layer (fail-open):** Three components are explicitly designed to fail open:
- `SemanticCache`: any exception in `lookup()` returns `None` (treated as cache miss), any exception in `store()` is logged and swallowed
- Rate limiter: Redis error returns `(True, 0)` — availability beats strict rate limiting
- Evaluation result cache: Redis failure proceeds without caching — eval runs, just slower

All fail-open paths log a `WARNING` with `extra={"error_type": type(e).__name__}` for observability.

See also: [API Reference — Rate Limits](api-reference.md#rate-limits) and [Semantic Cache — Failure Mode](semantic-cache.md#failure-mode) for component-specific fail-open behavior.

## Observability Stack

**Structured logging:** Every log line carries `request_id` (from `RequestIDFilter`), log level, module name, and any structured fields passed via `extra={...}`. Log format switches between human-readable (`verbose`) and machine-parseable JSON (`json`) via `LOG_FORMAT` env var. Same code path for both — only the formatter changes. In production, JSON goes to Datadog/CloudWatch/stdout.

**LangSmith tracing:** Every LLM provider method (`OpenAIProvider.stream`, `AnthropicProvider.stream`, etc.) is decorated with `@traceable(run_type="llm")`. When `LANGCHAIN_TRACING_V2=true`, LangSmith captures the full span tree for each request. When disabled, `@traceable` is a no-op — zero performance impact.

**Flower dashboard:** Celery task monitoring at `http://localhost:5555`. Requires `FLOWER_USER` and `FLOWER_PASSWORD` from `.env`. Shows task state, retry count, worker health, and queue depth in real time.

## Deployment Topology

Five Docker Compose services, all with health checks and persistent volumes:

| Service | Port | Purpose | Volume |
|---------|------|---------|--------|
| `postgres` (pgvector/pgvector:pg16) | 5432 | Relational data + vector embeddings | `postgres_data` |
| `redis` (redis:7-alpine) | 6379 | Celery broker + semantic cache + BM25 cache + rate limiter | `redis_data` |
| `flower` (mher/flower:2.0) | 5555 | Celery monitoring dashboard | — |
| `ollama` (ollama/ollama:latest) | 11434 | Local LLM runtime (no API key needed) | `ollama_data` |
| `minio` (minio/minio:latest) | 9000 (API), 9001 (UI) | S3-compatible file storage for uploaded documents | `minio_data` |

Django and the Celery worker run on the host (not in Docker) during local development — they connect to the services via `localhost:{port}`. `OLLAMA_KEEP_ALIVE=-1` keeps the model loaded in memory permanently, preventing the 30-60s cold-start penalty after idle.

For a complete setup walkthrough, see [docs/development.md](development.md).
