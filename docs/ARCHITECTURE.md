# DocuMind — System Architecture

## Architecture Philosophy

DocuMind follows Clean Architecture principles:
- Each layer has one responsibility
- Layers communicate through defined interfaces
- Business logic (retrieval, generation) never depends on infrastructure (database, HTTP)
- Every component is independently replaceable and testable

Practical meaning: if we want to swap Qdrant for a different vector database, we change
ONE file. If we want to swap Claude for GPT-4, we change ONE file. Nothing else breaks.

---

## System Diagram

```
┌──────────────────────────────────────────────────────────┐
│                     CLIENT LAYER                         │
│         HTTP Client  |  CLI  |  Web Browser              │
└────────────────────────┬─────────────────────────────────┘
                         │ HTTP
┌────────────────────────▼─────────────────────────────────┐
│           API LAYER  (Django + Django REST Framework)     │
│      Auth  |  Rate Limiting  |  Request Tracing           │
│                                                           │
│    /documents    /query    /analysis    /health           │
└──────┬──────────────────┬───────────────┬────────────────┘
       │                  │               │
┌──────▼──────┐  ┌────────▼──────┐  ┌────▼──────────────┐
│  INGESTION  │  │  QUERY ENGINE │  │  AGENT PIPELINE   │
│  PIPELINE   │  │               │  │                   │
│             │  │ 1. Embed Q    │  │ 1. Plan query     │
│ 1. Parse    │  │ 2. Hybrid     │  │ 2. Multi-hop      │
│ 2. Chunk    │  │    search     │  │    search         │
│ 3. Embed    │  │ 3. Rerank     │  │ 3. Synthesize     │
│ 4. Index    │  │ 4. Generate   │  │ 4. Self-evaluate  │
│             │  │ 5. Stream     │  │                   │
└──────┬──────┘  └────────┬──────┘  └───────────────────┘
       │                  │
┌──────▼──────────────────▼────────────────────────────────┐
│                  RETRIEVAL LAYER                          │
│                                                           │
│  ┌──────────────────┐      ┌─────────────────────────┐   │
│  │  pgvector        │      │  BM25 Keyword Index     │   │
│  │  (PostgreSQL     │      │  (Exact word matching)  │   │
│  │   extension)     │      │                         │   │
│  └────────┬─────────┘      └────────────┬────────────┘   │
│           │                             │                 │
│           └──────────────┬──────────────┘                 │
│                          │                                │
│               ┌──────────▼──────────┐                    │
│               │   Hybrid Fusion     │                    │
│               │   (RRF Algorithm)   │                    │
│               └──────────┬──────────┘                    │
│                          │                                │
│               ┌──────────▼──────────┐                    │
│               │   Cross-Encoder     │                    │
│               │   Re-Ranker         │                    │
│               └─────────────────────┘                    │
└──────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────────┐
│               INFRASTRUCTURE LAYER                        │
│                                                           │
│   PostgreSQL + pgvector              Redis                │
│   (metadata, job tracking,           (cache + jobs)       │
│    AND vector embeddings —                                │
│    one database does everything)                          │
│                                                           │
│   LangSmith       Local storage (raw document files)     │
│   (LLM tracing)                                           │
└──────────────────────────────────────────────────────────┘
```

---

## Folder Structure

```
documind/
│
├── PRODUCT_OVERVIEW.md       # What we are building and why
├── ARCHITECTURE.md           # This file
├── ROADMAP.md                # Milestones and phases
├── TASKS.md                  # Current sprint tasks and progress
├── PROJECT_CONTEXT.md        # Context file for new Claude sessions
├── DEV_COMMANDS.md           # Every command to run the project
│
├── manage.py                 # Django's command-line tool (run all Django commands through this)
├── docker-compose.yml        # Runs Postgres (with pgvector) + Redis locally
├── pyproject.toml            # Python dependencies
├── .env.example              # Environment variable template (safe to commit)
├── .env                      # Real secrets — NEVER commit this file
├── .gitignore
│
├── core/                     # Django project configuration (settings, routing)
│   ├── settings.py           # All Django settings loaded from .env
│   ├── urls.py               # Root URL router — wires all apps together
│   ├── wsgi.py               # Standard web server entry point
│   └── asgi.py               # Async entry point (needed for streaming responses)
│
│   # Django "apps" — each app owns one feature area
│   # (models, views, serializers, urls, migrations all live inside the app)
│
├── documents/                # Django app: document upload and management
│   ├── models.py             # Document and Job database tables
│   ├── serializers.py        # DRF: shapes for API request and response data
│   ├── views.py              # API logic: upload document, check job status
│   ├── urls.py               # /api/documents/ routes
│   ├── tasks.py              # Celery background tasks for PDF processing
│   ├── admin.py              # Register models in Django admin panel
│   └── migrations/           # Auto-generated migration files (track DB changes)
│
├── query/                    # Django app: question answering
│   ├── serializers.py        # Request/response shapes for query endpoints
│   ├── views.py              # API logic: receive question, return streamed answer
│   └── urls.py               # /api/query/ routes
│
├── analysis/                 # Django app: agent workflows
│   ├── serializers.py        # Request/response shapes for analysis endpoints
│   ├── views.py              # API logic: comparison, contradiction detection
│   └── urls.py               # /api/analysis/ routes
│
│   # Core modules — pure Python, no Django dependency
│   # These contain all AI logic and can be tested without running Django
│
├── ingestion/                # Step 1: Turn documents into indexed data
│   ├── parsers.py            # PDF/HTML/text → plain text
│   ├── chunkers.py           # Plain text → parent chunks → child chunks
│   ├── embedders.py          # Chunks → vectors (numbers)
│   └── pipeline.py           # Orchestrates: parse → chunk → embed → store
│
├── retrieval/                # Step 2: Find relevant content for a query
│   ├── vector_store.py       # pgvector: store and search vectors via PostgreSQL
│   ├── bm25.py               # BM25: keyword search
│   ├── hybrid.py             # Combine vector + keyword results with RRF
│   └── reranker.py           # Cross-encoder: re-score top 20 → return top 5
│
├── generation/               # Step 3: Generate answers from retrieved content
│   ├── llm.py                # LLM client: API calls, cost tracking, fallbacks
│   ├── prompts.py            # All prompt templates (versioned, never hardcoded)
│   ├── schemas.py            # Pydantic models for structured LLM outputs
│   └── streaming.py          # Stream tokens to Django response with citations
│
├── agents/                   # Step 4: Multi-step AI reasoning workflows
│   ├── tools.py              # Functions the agent can call (search, summarize)
│   ├── graph.py              # LangGraph: agent as a state machine
│   ├── query_planner.py      # Break complex queries into sub-questions
│   └── executor.py           # Run agent safely with error handling and logging
│
├── evaluation/               # Step 5: Measure whether the system is working
│   ├── metrics.py            # Faithfulness, relevancy, recall calculations
│   ├── datasets.py           # Load and manage eval ground-truth datasets
│   ├── harness.py            # Run full evaluation suite automatically
│   └── reports.py            # Format and save evaluation results
│
├── tests/
│   ├── unit/                 # Fast, isolated tests (no database needed)
│   ├── integration/          # Tests that use real database and services
│   └── evals/
│       ├── datasets/         # JSON files with ground-truth Q&A pairs
│       └── run_evals.py
│
└── scripts/
    ├── ingest_demo.py        # Load sample documents to test the system
    └── benchmark.py         # Measure retrieval precision vs baseline
```

---

## Tech Stack — Every Choice Explained for Beginners

### Python 3.12
The language we write all code in. Python is the industry standard for AI
engineering. It reads almost like English and has the largest AI library
ecosystem in the world.

### uv (Package Manager)
Installs Python libraries and manages the project environment. Think of it
as an app store for code libraries. Modern replacement for pip — faster and
more reliable.

### Django 4.2 (Web Framework)
The most widely used Python web framework in the industry. Django handles
incoming HTTP requests, URL routing, authentication, admin panels, and
database management — all built in. It is the framework most Python backend
jobs require. Chosen for maximum job-market relevance. Used by Instagram,
Pinterest, Disqus, and thousands of companies worldwide.

### Django REST Framework (DRF)
An extension to Django specifically for building REST APIs. Adds serializers
(for request/response data shapes), viewsets, authentication, and permissions.
DRF is mentioned in the majority of Python backend job postings. It is the
industry standard for building APIs on top of Django.

### Django ORM + Django Migrations
Django's built-in way to talk to PostgreSQL using Python instead of raw SQL.
You define your database tables as Python classes (models), and Django
translates them into SQL automatically. Migrations track every change to your
database structure over time — like a version history for your database.
No separate tool needed: it is built into Django.

### PostgreSQL (Relational Database)
Stores structured data in tables with rows and columns. We use it for:
document metadata (filename, upload date, status), job tracking, and
evaluation results. Think of it as a highly reliable spreadsheet.

### pgvector (Vector Search via PostgreSQL)
pgvector is a PostgreSQL extension that adds vector similarity search
directly to your existing PostgreSQL database. Instead of running a
separate vector database service, we add one extension to PostgreSQL
and it handles both relational data AND vector search in one place.

Why this matters:
- No extra Docker container — PostgreSQL already runs in our stack
- Simpler infrastructure — one database instead of two
- Django ORM support — query vectors using the same ORM you already know
- Used by most companies on a PostgreSQL + Django stack
- Resume line: "pgvector for vector similarity search on PostgreSQL"

How it works: we add a `vector` column type to a PostgreSQL table.
Each document chunk gets its embedding stored as a vector in that column.
When searching, PostgreSQL computes cosine similarity against all vectors
and returns the most similar ones.

### Redis
Two roles:
1. Cache: Store results of expensive operations so identical queries
   return instantly without re-running.
2. Task queue: Background job management for document processing.

### Celery
Runs background tasks. When a user uploads a PDF, we don't make them
wait while we process it. Celery picks up the job in the background
and processes it while the user does something else.

### OpenAI + Anthropic Claude (LLM Providers)
Two LLM providers, both integrated:
- OpenAI GPT-4o-mini: Fast and cheap. Used for simple tasks.
- OpenAI GPT-4o: Powerful. Most job postings mention OpenAI experience.
- Anthropic Claude Sonnet: Best reasoning. Fallback for complex tasks.
We route to the right model based on task complexity and cost budget.
Knowing both providers is what employers expect from an AI engineer.

### Instructor
Forces Claude to return structured Python objects instead of raw text.
When we ask for "a list of contradictions", we get back a validated
Python list — not a paragraph we have to parse manually.

### sentence-transformers
Two uses:
1. Embedding model: Converts text to vectors for Qdrant storage.
2. Cross-encoder re-ranker: Re-scores retrieval results with higher
   accuracy than the initial search. The step that dramatically
   improves retrieval quality.

### rank-bm25
BM25 keyword search — the same algorithm Elasticsearch uses internally.
Finds exact keyword matches, proper names, and rare terms that semantic
search misses. Combined with vector search for hybrid retrieval.

### LangChain + LangGraph
LangChain is the most widely mentioned AI framework in job postings.
It provides building blocks for LLM applications: chains, retrievers,
document loaders, and memory. LangGraph extends LangChain specifically
for agents — it models the agent as a state machine where each step
is a node and transitions are edges. Makes agent behavior debuggable,
predictable, and recoverable from failures.

### LangSmith
Observability for every LLM call. Records: what prompt was sent,
what tokens were used, what the response was, latency, cost.
How production AI teams debug and improve their systems.

### Docker + Docker Compose
Runs PostgreSQL, Qdrant, and Redis in isolated containers locally.
One command starts everything. Eliminates environment setup problems.

---

## Key Design Decisions

### Decision 1: Hierarchical Chunking
Documents are split into two levels:
- Child chunks (128 tokens): Small, precise. Used for retrieval.
- Parent chunks (512 tokens): Larger context. Sent to the LLM.

Each child chunk knows its parent. We retrieve with child chunks
(precision), we read with parent chunks (context). This is better
than sending large chunks to the retrieval system or small chunks
to the LLM.

### Decision 2: Hybrid Search with RRF
We run semantic search and keyword search in parallel, then combine
results using Reciprocal Rank Fusion:

  score = 1/(rank_in_semantic + 60) + 1/(rank_in_keyword + 60)

No tuning required. The top-ranked results from both systems naturally
rise to the top. Consistently outperforms either method alone.

### Decision 3: Two-Stage Retrieval
Stage 1 — Fast: Hybrid search retrieves top 20 candidates.
Stage 2 — Precise: Cross-encoder re-scores all 20, returns top 5.

The cross-encoder is 10x slower than embedding search but significantly
more accurate. Running it on 20 candidates (not the whole database)
keeps latency acceptable while dramatically improving quality.

### Decision 4: Agent vs. Direct Query
Simple factual question → Direct query engine (fast, cheap, reliable)
Complex multi-part question → Agent pipeline (plans, iterates, synthesizes)

The system classifies query complexity before routing. This prevents
unnecessary agent overhead for simple lookups.

### Decision 5: Environment Variables for All Secrets
API keys, database URLs, and passwords live in a .env file.
This file is in .gitignore — it never touches GitHub.
The config.py file loads all values at startup using pydantic-settings.
If a required value is missing, the app refuses to start with a clear error.

---

## Data Flows

### Flow 1: Document Upload

```
User uploads PDF
      │
      ▼
POST /documents
      │
      ▼
Save file to disk → Create job record in PostgreSQL (status: pending)
      │
      ▼
Return: { "job_id": "abc123", "status": "pending" }
      │
      ▼ (background — user does not wait)
Celery worker picks up job
      │
      ├── Parser: PDF → plain text
      ├── Chunker: text → parent chunks (512 tokens)
      ├── Chunker: parent chunks → child chunks (128 tokens)
      ├── Embedder: child chunks → vectors
      ├── Qdrant: store vectors + metadata
      ├── BM25: update keyword index
      └── PostgreSQL: update job status to "completed"
```

### Flow 2: Question & Answer

```
User asks: "What are the main risks mentioned?"
      │
      ▼
POST /query
      │
      ▼
Classify complexity → Simple → Direct Query Engine
      │
      ├── Embed the question (text → vector)
      ├── Qdrant: semantic search → top 20 chunks
      ├── BM25: keyword search → top 20 chunks
      ├── Hybrid fusion (RRF) → combined top 20
      ├── Cross-encoder: re-rank → top 5 chunks
      ├── Build prompt: [system] + [5 chunks as context] + [question]
      ├── Call Claude API (streaming enabled)
      ├── Stream tokens to user with inline citations
      ├── Log full trace to LangSmith
      └── Record cost (tokens × price)
```

### Flow 3: Agent Workflow (Complex Query)

```
User asks: "Compare the risk sections of document A and document B
            and identify any contradictions"
      │
      ▼
Classify complexity → Complex → Agent Pipeline (LangGraph)
      │
      ├── Node 1: Query Planner
      │     Break into sub-questions:
      │     Q1: "What risks does document A mention?"
      │     Q2: "What risks does document B mention?"
      │     Q3: "Which risks appear in one but not the other?"
      │
      ├── Node 2: Executor (loops for each sub-question)
      │     Run retrieval + generation for each sub-question
      │     Accumulate answers in agent state
      │
      ├── Node 3: Synthesizer
      │     Combine all sub-answers into a final structured response
      │     Format: agreements, differences, contradictions
      │
      └── Node 4: Self-Evaluator
            Does the answer actually address the original question?
            If not → loop back to Node 2 with refined queries
            If yes → stream final response to user
```
