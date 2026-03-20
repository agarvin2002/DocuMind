# DocuMind — Development Roadmap

## How to Read This Roadmap

Each Phase builds on the previous one. Never skip a phase.
Each phase has a clear goal and a definition of "done" — you know exactly
when a phase is complete before moving to the next.

Current Phase: PHASE 1 (not started)

---

## Phase 1: Project Foundation
**Goal:** The project runs locally. Infrastructure is up. We can connect to all databases.

### What We Build
- Python project structure with uv
- Docker Compose: Postgres + Qdrant + Redis running locally
- Environment variable configuration
- Database models and first migration
- Health check API endpoint
- Basic FastAPI app that starts without errors

### Definition of Done
- [ ] `docker-compose up` starts all services without errors
- [ ] `uv run uvicorn` starts the API server
- [ ] GET /health returns `{"status": "ok"}`
- [ ] Can connect to PostgreSQL and create tables
- [ ] Can connect to Qdrant and create a collection
- [ ] Can connect to Redis
- [ ] .env.example is documented with all required variables
- [ ] .gitignore correctly excludes .env and sensitive files

### Skills Learned
- Project structure and Python packaging
- Docker and Docker Compose
- Environment variable management
- Database connection management
- Basic FastAPI routing

---

## Phase 2: Document Ingestion Pipeline
**Goal:** Upload a PDF and have it parsed, chunked, embedded, and stored in Qdrant.

### What We Build
- PDF parser (extract text from PDF files)
- Text chunker with hierarchical strategy (parent + child chunks)
- Embedding model integration (sentence-transformers)
- Qdrant vector store interface
- Celery background task for async processing
- POST /documents API endpoint
- GET /documents/{id} endpoint to check job status
- BM25 keyword index updated on ingestion

### Definition of Done
- [ ] Upload a PDF via POST /documents
- [ ] Job is processed in background (not blocking the API)
- [ ] Text is extracted from PDF correctly
- [ ] Document is split into parent chunks (512 tokens) and child chunks (128 tokens)
- [ ] Child chunks are embedded and stored in Qdrant
- [ ] BM25 index is updated with document text
- [ ] Job status changes from "pending" → "processing" → "completed"
- [ ] GET /documents/{id} returns job status and document metadata

### Skills Learned
- File upload handling
- PDF parsing
- Text chunking strategies
- Vector embeddings
- Qdrant vector storage
- Celery background tasks
- Redis task queue

---

## Phase 3: Retrieval System
**Goal:** Given a question, retrieve the most relevant document chunks accurately.

### What We Build
- Semantic search via Qdrant (vector similarity)
- BM25 keyword search
- Hybrid fusion with RRF algorithm
- Cross-encoder re-ranking
- Retrieval pipeline that combines all three steps
- Benchmark script to measure retrieval quality

### Definition of Done
- [ ] Semantic search returns relevant chunks for a test question
- [ ] BM25 search returns results for exact keyword queries
- [ ] Hybrid search combines both results correctly
- [ ] Cross-encoder re-ranks results (top 5 from top 20)
- [ ] benchmark.py measures retrieval precision@5 against a baseline
- [ ] Hybrid + reranking beats naive vector-only search in benchmarks

### Skills Learned
- Vector similarity search
- BM25 keyword search
- Reciprocal Rank Fusion algorithm
- Cross-encoder models
- Retrieval evaluation and benchmarking

---

## Phase 4: LLM Generation + Streaming
**Goal:** Take retrieved chunks, generate a grounded answer, stream it with citations.

### What We Build
- Claude API client with cost tracking and fallback
- Prompt templates (versioned, not hardcoded)
- Structured output schemas with Instructor
- Streaming response handler
- Citation injection during streaming
- POST /query endpoint (streaming)
- LangSmith tracing integration

### Definition of Done
- [ ] POST /query returns a streaming response
- [ ] Answer is grounded in retrieved documents (no hallucinations)
- [ ] Every claim has an inline citation [1], [2] etc.
- [ ] Token usage and cost are logged per query
- [ ] Full LLM trace visible in LangSmith dashboard
- [ ] Fallback to secondary model if primary fails
- [ ] Structured outputs validated by Pydantic (no raw text parsing)

### Skills Learned
- Claude API integration
- Streaming HTTP responses (Server-Sent Events)
- Prompt engineering
- Structured outputs with Instructor
- LLM observability with LangSmith
- Cost tracking and optimization

---

## Phase 5: AI Agent Pipeline
**Goal:** Handle complex multi-part questions with a LangGraph agent that plans, searches, and synthesizes.

### What We Build
- Query complexity classifier (simple vs complex)
- LangGraph state machine for the agent
- Query decomposition: break one question into sub-questions
- Multi-hop search: run retrieval for each sub-question
- Result synthesizer: combine all sub-answers
- Document comparison workflow
- Contradiction detection workflow
- POST /analysis endpoint

### Definition of Done
- [ ] Complex queries are routed to the agent (not direct query engine)
- [ ] Agent decomposes a complex question into 2-4 sub-questions
- [ ] Each sub-question is retrieved and answered independently
- [ ] Final answer synthesizes all sub-answers coherently
- [ ] Document comparison workflow returns structured diff
- [ ] Contradiction detection returns specific conflicting claims with sources
- [ ] Agent state is visible in LangSmith traces
- [ ] Agent handles failures gracefully (no infinite loops)

### Skills Learned
- LangGraph state machines
- AI agent design patterns
- Query decomposition
- Multi-hop reasoning
- Tool use in AI agents
- Agent error handling and recovery

---

## Phase 6: Evaluation Framework
**Goal:** Measure whether the system is actually working with real metrics.

### What We Build
- Eval dataset: 50+ ground-truth question-answer pairs
- RAGAS metrics: faithfulness, answer relevancy, context recall
- Custom eval harness that runs automatically
- Benchmark comparison: our system vs naive RAG baseline
- Evaluation report generator
- GitHub Actions CI: run evals on every PR

### Definition of Done
- [x] 50 ground-truth Q&A pairs created for test documents (17 ai_concepts, 17 product_spec, 16 science_report)
- [x] Faithfulness score > 0.85 (answers grounded in sources) — threshold enforced in evaluation/constants.py
- [x] Answer relevancy score > 0.80 — threshold enforced in evaluation/constants.py
- [x] Context recall > 0.75 — threshold enforced in evaluation/constants.py
- [x] Our system beats naive RAG baseline by at least 20% — enforced in _determine_verdict()
- [x] Eval report generated as JSON + human-readable summary — evaluation/reports.py
- [x] GitHub Actions eval.yml runs on every push to main, uploads report as artifact
- [ ] Numbers documented in README with methodology (Phase 7)

### Skills Learned
- RAG evaluation methodology
- RAGAS framework
- Building automated eval pipelines
- Regression testing for AI systems
- Benchmarking and statistical measurement

---

## Phase 7: Production Readiness
**Goal:** The system is secure, monitored, documented, and ready to present.

### What We Build
- API key authentication
- Rate limiting per API key
- Semantic caching (skip LLM for near-identical queries)
- Request/response logging middleware
- Error handling: every endpoint returns structured error responses
- README with demo GIF, architecture diagram, benchmark results
- Docker Compose production configuration
- Environment variable documentation

### Definition of Done
- [ ] Unauthenticated requests return 401
- [ ] Rate limit exceeded returns 429
- [ ] Semantic cache reduces LLM calls by >30% on repeated queries
- [ ] All errors return structured JSON: {"error": "...", "code": "..."}
- [ ] README includes: demo GIF, architecture diagram, benchmark numbers
- [ ] New developer can run the project with 3 commands from the README
- [ ] No secrets in Git history

### Skills Learned
- API authentication
- Rate limiting
- Semantic caching
- Production error handling
- Technical documentation
- Security fundamentals

---

## Summary Timeline

| Phase | What Gets Built | Key Skill |
|-------|----------------|-----------|
| 1: Foundation | Docker, database, config, health API | Project setup |
| 2: Ingestion | PDF parsing, chunking, embedding, vector store | Data pipeline |
| 3: Retrieval | Hybrid search, reranking | RAG retrieval |
| 4: Generation | LLM integration, streaming, citations | LLM engineering |
| 5: Agents | LangGraph agent, multi-hop, comparison | AI agents |
| 6: Evaluation | Eval pipeline, RAGAS metrics, benchmarks | Production thinking |
| 7: Production | Auth, caching, docs, polish | Shipping software |

---

## Important Rules

1. Complete each phase fully before moving to the next
2. Check every item in "Definition of Done" before advancing
3. Run all existing tests before starting a new phase
4. Update TASKS.md at the end of every work session
5. Commit working code to Git at the end of every phase
