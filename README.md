# DocuMind

A production-grade RAG system with hybrid search, streaming generation, and a LangGraph agent pipeline — built with Python, Django, and pgvector.

## What Makes This Non-Trivial

- **Hierarchical chunking:** 128-token child windows are embedded and indexed for retrieval precision; 512-token parent windows are sent to the LLM for richer generation context. "Retrieve small, generate large" — separating indexing accuracy from answer quality.

- **Three-stage hybrid retrieval:** pgvector cosine similarity + BM25 keyword search, fused with Reciprocal Rank Fusion (k=60, Cormack et al. 2009), then re-ranked by `cross-encoder/ms-marco-MiniLM-L-6-v2`. Each stage catches what the others miss — vector search handles semantic equivalents, BM25 handles exact keyword matches, cross-encoder runs full attention over query+chunk pairs.

- **Semantic cache:** pgvector HNSW index with cosine distance ≤ 0.08 (92% similarity threshold), 7-day TTL. Semantically equivalent questions ("What are the main risks?" and "What risks does this document describe?") hit cache even with different phrasing. Fail-open — any cache failure falls through silently to the LLM pipeline.

- **LLM fallback chain:** OpenAI GPT-4o → Anthropic Claude → AWS Bedrock → Ollama, implemented as a Chain of Responsibility via `LLMProviderPort` structural Protocol. Adding a new provider requires zero changes to `FallbackLLMClient` — just append to the providers list at the composition root.

- **Agent pipeline:** LangGraph state machine classifies queries into four workflow types (`simple`, `multi_hop`, `comparison`, `contradiction`) and routes accordingly. Runs asynchronously via Celery with 202 Accepted + status polling. Nodes never raise to the graph engine — they set `state["error"]` and routing detects it, keeping every execution structurally complete.

- **Auth + rate limiting:** SHA-256 hashed API keys (plaintext never stored, shown once on creation), per-endpoint sliding-window rate limiting via Redis Lua script (atomic, fail-open on Redis error).

- **Evaluation:** RAGAS metrics (faithfulness, answer_relevancy, context_recall) run weekly via GitHub Actions, compared against a BM25-only naive baseline. Pass threshold: ≥20% improvement across all three metrics.

## Architecture

```
─── Upload & Ingestion ───────────────────────────────────────────────────────

POST /api/v1/documents/
  → save file to MinIO/S3
  → Document (status=PENDING)
  → Celery: ingest_document

  IngestionPipeline.run()  [pure Python — no Django imports]
    ├── Parser (pypdf)            → pages with page numbers
    ├── HierarchicalChunker       → child (128 tok) + parent (512 tok) pairs
    ├── SentenceTransformerEmbedder → 384-dim vectors (all-MiniLM-L6-v2)
    └── BM25Index.build()         → keyword index

  → bulk_create DocumentChunks (pgvector)
  → save BM25 index (Redis, 7-day TTL)
  → Document (status=READY)

─── Query / Ask (Streaming) ──────────────────────────────────────────────────

POST /api/v1/query/ask/
  → SemanticCache.lookup()  [pgvector HNSW, cosine distance ≤ 0.08]
      ├── HIT  → stream cached answer → SSE citations → SSE done
      └── MISS → continue

  → RetrievalPipeline.run()
      ├── embed query (SentenceTransformer)
      ├── [parallel] VectorStore.search()  → top k*3 (pgvector <=>)
      ├── [parallel] BM25Index.search()    → top k*3 (Redis)
      ├── HybridFusion.fuse()              → RRF k=60
      └── CrossEncoderReranker.rerank()    → ms-marco-MiniLM-L-6-v2

  → FallbackLLMClient.stream()  [OpenAI → Anthropic → Bedrock → Ollama]
      → SSE token events
      → _resolve_citations()   → [1][2] markers → chunk metadata
      → SSE citations event
      → SSE done event
  → SemanticCache.store()

─── Agent Analysis (Async) ───────────────────────────────────────────────────

POST /api/v1/analysis/
  → AnalysisJob (status=PENDING)
  → 202 Accepted {job_id}
  → Celery: run_analysis_task

  AgentExecutor → LangGraph state machine
    ├── classify_query_node   → workflow_type (Instructor structured output)
    │
    ├── [simple]        simple_passthrough_node → END
    ├── [multi_hop]     plan → retrieve×N → generate×N → synthesize → END
    ├── [comparison]    retrieve from each doc → comparison_generate → END
    └── [contradiction] retrieve from each doc → contradiction_detect → END

  → AnalysisJob (status=COMPLETE, result_data=JSON)
  → cache in Redis

GET /api/v1/analysis/{job_id}/  → Redis cache → PostgreSQL fallback
```

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| API | Django 4.2 + DRF | Batteries-included, production patterns, OpenAPI via drf-spectacular |
| Vector search | PostgreSQL + pgvector | No separate vector DB; HNSW index; same instance as relational data |
| Embeddings | all-MiniLM-L6-v2 (384-dim) | Fast, runs on CPU, no API cost, sentence-transformers |
| Reranker | ms-marco-MiniLM-L-6-v2 | Cross-encoder trained on MS MARCO, ~70MB, HuggingFace |
| Keyword search | rank-bm25 + Redis | Serialized BM25 index cached per document, deserialized in <10ms |
| Agent framework | LangGraph + LangChain | Typed state machine, clean conditional routing, compiled graph |
| Task queue | Celery + Redis | Async ingestion and agent jobs, Flower monitoring dashboard |
| File storage | MinIO (local) / S3 (prod) | Drop-in swap via django-storages, no code changes |
| LLM providers | OpenAI, Anthropic, Bedrock, Ollama | Chain of Responsibility, no vendor lock-in, local dev with zero API cost |
| Observability | LangSmith + python-json-logger | LLM span tracing, request-ID propagation, JSON in prod |
| Evaluation | RAGAS + GitHub Actions | Automated weekly regression against BM25-only baseline |

## Quick Start

```bash
# 1. Copy and fill in environment variables (see docs/development.md)
cp .env.example .env

# 2. Start all infrastructure services
docker compose up -d

# 3. One-time setup (first run only)
docker compose exec minio mc alias set local http://localhost:9000 documind documind123
docker compose exec minio mc mb local/documind-documents
docker compose exec ollama ollama pull qwen2.5:3b
uv run python manage.py migrate

# 4. Start the application (two terminals)
uv run python manage.py runserver          # Terminal 1 — Django
uv run celery -A core worker --loglevel=info  # Terminal 2 — Celery
```

Create an API key, then try the streaming ask endpoint:

```bash
uv run python manage.py create_api_key dev-key
# → dm_xxxx... (save this — shown once only)

# Upload a document
curl -X POST http://localhost:8000/api/v1/documents/ \
  -H "X-API-Key: dm_xxxx" \
  -F "title=My Document" -F "file=@/path/to/document.pdf"

# Stream a Q&A answer (SSE)
curl -X POST http://localhost:8000/api/v1/query/ask/ \
  -H "X-API-Key: dm_xxxx" -H "Content-Type: application/json" \
  --no-buffer \
  -d '{"query": "what are the key risks?", "document_id": "<doc-uuid>"}'
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/documents/` | Upload a document — triggers async ingestion pipeline |
| `GET` | `/api/v1/documents/{id}/` | Poll ingestion status (pending → processing → ready/failed) |
| `POST` | `/api/v1/query/search/` | Hybrid semantic search — returns ranked chunks |
| `POST` | `/api/v1/query/ask/` | Streaming Q&A with citations (Server-Sent Events) |
| `POST` | `/api/v1/analysis/` | Create async agent job — 202 Accepted with job_id |
| `GET` | `/api/v1/analysis/{id}/` | Poll agent job status and retrieve result |
| `GET` | `/api/v1/health/` | Health check (no auth required) |

Full API documentation with request/response examples: [docs/api-reference.md](docs/api-reference.md)

Interactive Swagger UI (when running locally): `http://localhost:8000/api/docs/`

## Documentation

| Document | What It Covers |
|----------|---------------|
| [Architecture](docs/architecture.md) | Module boundaries, dependency injection, data models, error handling contract |
| [Ingestion Pipeline](docs/ingestion.md) | Parse → chunk → embed → BM25 index, hierarchical chunking design, Celery task decisions |
| [Retrieval System](docs/retrieval.md) | Hybrid search, RRF algorithm, cross-encoder reranking, K value tuning |
| [Generation & Streaming](docs/generation.md) | SSE wire protocol, LLM provider abstraction, fallback chain, citation extraction |
| [Semantic Cache](docs/semantic-cache.md) | pgvector HNSW cache, similarity threshold math, invalidation contract |
| [Agent Pipeline](docs/agent-pipeline.md) | LangGraph state machine, 4 workflow types, error contract, async execution model |
| [API Reference](docs/api-reference.md) | All endpoints with request/response examples and curl commands |
| [Development Setup](docs/development.md) | Local setup, environment variables, smoke test walkthrough |
| [Testing Guide](docs/testing.md) | Running tests, protocol fakes philosophy, RAGAS evaluations |

## License

MIT
