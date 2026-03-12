# Phase 3 — Retrieval System: Implementation Plan

**Status:** Plan approved, implementation not started (2026-03-12)
**Branch:** `feature/retrieval-system`
**Depends on:** Phase 2 complete (PDF → chunks → embeddings → pgvector ✅)

---

## Goal

Given a user query + document_id, return the top-k most relevant chunks using:
1. Semantic vector search (pgvector cosine similarity)
2. BM25 keyword search (exact-match ranking)
3. RRF hybrid fusion (combines both ranked lists)
4. Cross-encoder re-ranking (scores query+chunk pairs directly)

**Endpoint delivered:**
```
POST /api/v1/query/search/
{"query": "...", "document_id": "uuid", "k": 10}

→ 200 {"query": "...", "document_id": "...", "results": [{chunk_id, document_title, page_number, child_text, parent_text, score}...]}
→ 404 if document not found or no relevant chunks
```

---

## Architecture

### Dependency Map

```
query/services.py  ← composition root: the ONLY place that imports from
│                    both retrieval/ and documents/ in the same function
│
├── ingestion/embedders.py        SentenceTransformerEmbedder.embed_single()
├── documents/selectors.py        vector_search_chunks(), keyword_search_chunks(),
│                                 get_bm25_index_or_rebuild()
├── retrieval/reranker.py         CrossEncoderReranker
└── retrieval/pipeline.py         RetrievalPipeline
      ├── retrieval/vector_store.py   VectorStore (adapter wrapping VectorSearchPort)
      ├── retrieval/hybrid.py         HybridFusion (RRF algorithm)
      └── retrieval/reranker.py       CrossEncoderReranker
```

**Clean Architecture boundary (never violate):**
`retrieval/` defines Protocols. `documents/selectors.py` implements them structurally
(duck typing — no explicit inheritance). `query/services.py` wires them together.
`retrieval/` never imports from `documents/` or any Django app.

---

## Components

### 1. `retrieval/schemas.py` — ChunkSearchResult

Pure Python dataclass. The universal result object flowing through all retrieval components.

```python
@dataclass
class ChunkSearchResult:
    chunk_id: str        # UUID string
    document_id: str     # UUID string
    document_title: str  # for citation in Phase 4
    chunk_index: int     # position in document — maps BM25 corpus position back to DB row
    child_text: str      # small text that was indexed (128 tokens)
    parent_text: str     # wide context sent to LLM in Phase 4 (512 tokens)
    page_number: int     # source page for citation
    score: float         # relevance score — higher is better
```

No Django. No imports. Just data.

---

### 2. `retrieval/protocols.py` — Port Protocols

Four structural Protocol contracts. `retrieval/` defines them; other modules implement them
without importing this file (Python structural/duck typing).

```python
class QueryEmbedderPort(Protocol):
    def embed_single(self, text: str) -> list[float]: ...

class VectorSearchPort(Protocol):
    def __call__(self, embedding: list[float], document_id: uuid.UUID, k: int) -> list[ChunkSearchResult]: ...

class KeywordSearchPort(Protocol):
    def __call__(self, query: str, document_id: uuid.UUID, k: int) -> list[ChunkSearchResult]: ...

class RerankerPort(Protocol):
    def rerank(self, query: str, candidates: list[ChunkSearchResult]) -> list[ChunkSearchResult]: ...
```

---

### 3. `ingestion/embedders.py` + `ingestion/protocols.py` (modification)

Add `embed_single(text: str) -> list[float]` to `SentenceTransformerEmbedder`.
Implemented as `embed_batch([text])[0]` — no new model loading logic.
Update `EmbedderProtocol` in `ingestion/protocols.py` to include `embed_single`.
`SentenceTransformerEmbedder` satisfies `QueryEmbedderPort` structurally — no inheritance needed.

---

### 4. `retrieval/bm25.py` (modification)

Add `search(query_text, k) -> list[tuple[int, float]]` to `BM25Index`.
Returns `(corpus_position, score)` pairs. `corpus_position` == `chunk_index` for that document.
Callers in `documents/selectors.py` map positions → `DocumentChunk` rows.

```python
def search(self, query_text: str, k: int) -> list[tuple[int, float]]:
    """Top-k (corpus_position, bm25_score) pairs. corpus_position equals chunk_index."""
```

---

### 5. `documents/selectors.py` (modification — 3 new functions)

**`vector_search_chunks(embedding, document_id, k) → list[ChunkSearchResult]`**
Uses pgvector `CosineDistance("embedding", embedding)` annotation via Django ORM.
Filters by `document_id`. Converts `DocumentChunk` rows → `ChunkSearchResult`.

**`keyword_search_chunks(query, document_id, k) → list[ChunkSearchResult]`**
Calls `get_bm25_index_or_rebuild()`, runs `bm25_index.search(query, k)`.
Maps corpus positions → `chunk_index` → fetches matching `DocumentChunk` rows.
Attaches BM25 scores to `ChunkSearchResult`.

**`get_bm25_index_or_rebuild(document_id) → BM25Index`**
1. Try Redis: `GET documind:bm25:{document_id}` → `BM25Index.from_bytes()`
2. Cache miss: load all `DocumentChunk.child_text` ordered by `chunk_index`,
   call `BM25Index.build()`, persist to Redis (TTL: 7 days / 604800 seconds)
3. Log cache hit/miss for observability

---

### 6. `documents/services.py` (modification)

Add `save_bm25_index(document_id, bm25_index)`:
- Serialize with `bm25_index.serialize()` → bytes
- Store in Redis: key `documind:bm25:{document_id}`, TTL 7 days
- Redis connection: `socket_connect_timeout=2, socket_timeout=2`
- `try/finally` with `r = None` guard per project Redis pattern

---

### 7. `documents/tasks.py` (modification — 1 line)

After `save_document_chunks()` add:
```python
save_bm25_index(document_id, result.bm25_index)
```
Phase 2 built the BM25 index but never persisted it. This closes that gap.

---

### 8. `retrieval/vector_store.py` — VectorStore

Thin adapter wrapping `VectorSearchPort`. Adds logging and error handling.
Callers depend on this class, not the raw selector function.

```python
class VectorStore:
    def __init__(self, search_fn: VectorSearchPort) -> None: ...
    def search(self, embedding, document_id, k) -> list[ChunkSearchResult]: ...
```

---

### 9. `retrieval/hybrid.py` — HybridFusion (RRF)

Pure algorithm — no I/O, no Django, no models. Merges two ranked lists using
Reciprocal Rank Fusion.

**RRF formula:** `score(chunk) = Σ 1 / (k + rank)` across all lists where chunk appears.
`k=60` is the standard constant. Chunks in both lists accumulate higher scores.

```python
class HybridFusion:
    def __init__(self, k: int = 60) -> None: ...
    def fuse(
        self,
        vector_results: list[ChunkSearchResult],
        keyword_results: list[ChunkSearchResult],
    ) -> list[ChunkSearchResult]: ...
```

Handles empty lists gracefully — if keyword results are empty, returns vector results ranked by RRF scores alone.

---

### 10. `retrieval/reranker.py` — CrossEncoderReranker

Uses `sentence_transformers.CrossEncoder` (already installed — part of `sentence-transformers`).
Model: `cross-encoder/ms-marco-MiniLM-L-6-v2` (~70MB, auto-downloaded on first call).
Lazy-loaded — same pattern as `SentenceTransformerEmbedder`.

Difference from embedding: cross-encoder reads query AND passage *together*,
allowing the model to score their relationship directly. More accurate, slower.
Only runs on top `k * candidate_multiplier` candidates from fusion — never the full corpus.

```python
class CrossEncoderReranker:
    def __init__(self, model_name: str | None = None) -> None: ...
    def rerank(self, query: str, candidates: list[ChunkSearchResult]) -> list[ChunkSearchResult]: ...
    # pairs = [(query, c.child_text) for c in candidates]
    # scores = self._model.predict(pairs)  → updates .score, re-sorts descending
```

---

### 11. `retrieval/pipeline.py` — RetrievalPipeline

Orchestrates all retrieval steps in order.

```python
class RetrievalPipeline:
    def __init__(
        self,
        embedder: QueryEmbedderPort,
        vector_search_fn: VectorSearchPort,
        keyword_search_fn: KeywordSearchPort,
        reranker: RerankerPort,
        candidate_multiplier: int = 3,
    ) -> None: ...

    def run(self, query: str, document_id: uuid.UUID, k: int = 10) -> list[ChunkSearchResult]:
        # 1. embed query  →  384-dim vector
        # 2. vector search  →  top k*3 candidates
        # 3. keyword search  →  top k*3 candidates (empty list = graceful fallback)
        # 4. RRF fusion  →  merged ranked list
        # 5. cross-encoder rerank  →  final scored list
        # 6. return top k
```

`candidate_multiplier=3`: fetch 30 to get the best 10. Gives fusion and reranker
enough material to promote the right results.

---

### 12. `query/services.py` — execute_search (composition root)

The single place that assembles the full pipeline from both worlds.

```python
def execute_search(query: str, document_id: uuid.UUID, k: int = 10) -> list[ChunkSearchResult]:
    # local imports to avoid circular chains at module load time
    from ingestion.embedders import SentenceTransformerEmbedder
    from documents.selectors import vector_search_chunks, keyword_search_chunks
    from retrieval.reranker import CrossEncoderReranker
    from retrieval.pipeline import RetrievalPipeline

    pipeline = RetrievalPipeline(
        embedder=SentenceTransformerEmbedder(),
        vector_search_fn=vector_search_chunks,
        keyword_search_fn=keyword_search_chunks,
        reranker=CrossEncoderReranker(),
    )
    results = pipeline.run(query=query, document_id=document_id, k=k)
    if not results:
        raise NoRelevantChunksError(...)  # 404 — already defined in query/exceptions.py
    return results
```

---

### 13. `query/serializers.py`, `query/views.py`, `query/urls.py`

**Request:** `{query: str, document_id: UUID, k: int (default 10, max 50)}`
**Response:** `{query, document_id, results: [ChunkSearchResult fields...]}`
**View:** validates request → calls `execute_search()` → returns 200. Catches
`DocumentNotFoundError` (404) and `NoRelevantChunksError` (404).

---

## Task Order

| # | Task | File(s) |
|---|---|---|
| 3.1 | ChunkSearchResult dataclass | `retrieval/schemas.py` (new) |
| 3.2 | Port protocols | `retrieval/protocols.py` (new) |
| 3.3 | embed_single() | `ingestion/embedders.py`, `ingestion/protocols.py` |
| 3.4 | BM25 search method | `retrieval/bm25.py` |
| 3.5 | Vector + keyword selectors | `documents/selectors.py` |
| 3.6 | BM25 Redis persistence | `documents/services.py` |
| 3.7 | Persist BM25 after ingestion | `documents/tasks.py` |
| 3.8 | VectorStore adapter | `retrieval/vector_store.py` |
| 3.9 | HybridFusion RRF | `retrieval/hybrid.py` |
| 3.10 | CrossEncoderReranker | `retrieval/reranker.py` |
| 3.11 | RetrievalPipeline | `retrieval/pipeline.py` |
| 3.12 | Search serializers | `query/serializers.py` (new) |
| 3.13 | execute_search service | `query/services.py` |
| 3.14 | SearchView + routing | `query/views.py`, `query/urls.py` |
| 3.15 | Include query URLs | `core/urls.py` |
| 3.16 | Unit tests | `tests/unit/test_retrieval.py` (new) |
| 3.17 | Integration tests | `tests/integration/test_search.py` (new) |
| 3.18 | Quality gate | ruff + pytest + manage.py check — all green before PR |

---

## No New Dependencies

`sentence-transformers` is already installed — `CrossEncoder` is part of the package.
`redis` is already available via Celery infrastructure.
`pgvector` is already installed.

---

## Pre-PR Checklist

- [ ] `grep -r "from django\|import django" retrieval/` → zero results
- [ ] `uv run ruff check .` → clean
- [ ] `uv run pytest tests/ -v` → all pass
- [ ] `uv run python manage.py check` → no issues
- [ ] BM25 key present in Redis after uploading a document: `redis-cli GET documind:bm25:{id}`
- [ ] `POST /api/v1/query/search/` with a real document → results with scores

---

## What This Unlocks for Phase 4

Phase 4 takes the `parent_text` fields from these `ChunkSearchResult` objects and feeds them
to GPT-4o as context to generate a natural-language answer with page citations.
Phase 3 is the retrieval quality foundation — poor retrieval means poor answers
regardless of LLM quality.
