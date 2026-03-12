# Phase 3 — Retrieval System: Complete Teaching Guide

**Who this is for:** Someone who knows JavaScript/Node.js and is learning Python/Django.
**How to use this:** Read one Stop at a time. Each Stop is one file. Understand it fully before moving on.
**Golden rule:** Every concept is explained with a real-world analogy first. Code comes last.

---

## The Big Picture First

Before looking at any file, understand what Phase 3 does in plain English.

In Phase 2, you built a **library**. Every PDF you upload becomes rows of shelves, each shelf holding a short text passage (chunk). Each passage has a "meaning fingerprint" (embedding) attached.

Phase 3 builds the **librarian**. When someone asks a question, the librarian needs to find the 3-10 most relevant passages from all those shelves. The librarian uses three techniques:

**Technique 1 — Semantic search:** Understand the *meaning* of the question, not just the words. *"What are the risks?"* finds *"potential hazards include..."* — different words, same meaning.

**Technique 2 — Keyword search (BM25):** Find passages that contain the exact words from the question. Good for technical terms, names, codes. *"RFC 2119 MUST requirement"* — exact words matter.

**Technique 3 — Hybrid fusion + re-ranking:** Combine both search results into one smarter list. Then do one final careful pass where the model reads the question AND each passage together to score how well they actually match.

The result: a ranked list of the most relevant passages, ready to be sent to the LLM in Phase 4.

---

## The Files Built in Phase 3

```
retrieval/schemas.py        ← Stop 1:  the "result form"
retrieval/protocols.py      ← Stop 2:  the "socket shapes"
ingestion/embedders.py      ← Stop 3:  small addition — embed_single()
retrieval/bm25.py           ← Stop 4:  keyword search method added
documents/selectors.py      ← Stop 5:  the actual database search functions
documents/services.py       ← Stop 6:  saving BM25 to Redis
documents/tasks.py          ← Stop 7:  one new line wires everything together
retrieval/vector_store.py   ← Stop 8:  the vector search adapter
retrieval/hybrid.py         ← Stop 9:  the RRF fusion algorithm
retrieval/reranker.py       ← Stop 10: the cross-encoder re-ranker
retrieval/pipeline.py       ← Stop 11: the orchestrator
query/serializers.py        ← Stop 12: request/response validation
query/services.py           ← Stop 13: the composition root
query/views.py + urls.py    ← Stop 14: the HTTP endpoint
```

---

## Stop 1 — `retrieval/schemas.py` — The Result Form

### What is it?

A file with one thing: a `ChunkSearchResult` — a container that holds all information about one retrieved chunk.

### Why does it exist?

The retrieval pipeline has many steps: vector search, BM25 search, fusion, reranking. Each step takes chunks in and passes chunks out. They all need a shared language — a common format for "one chunk result."

Without this, each step would have its own format and you'd spend all your time converting between them. With this, every step speaks the same language.

### Real-world analogy

You're a hospital. A patient goes through Triage → Doctor → Pharmacy → Billing. Each department needs the patient's information. Instead of each department keeping their own separate notes in their own format, you give the patient a **standard medical form** when they arrive. Every department reads and fills in the same form. The form travels with the patient.

`ChunkSearchResult` is that standard form. It travels through the entire retrieval pipeline.

### New Python concept: What is a `@dataclass`?

In normal Python, to create an object with fields, you write:

```python
class ChunkSearchResult:
    def __init__(self, chunk_id, score, child_text, ...):
        self.chunk_id = chunk_id
        self.score = score
        self.child_text = child_text
        # ... 5 more lines of repetitive self.x = x
```

That's tedious and repetitive. Python has a shortcut called `@dataclass`. You write it once above the class, and Python automatically generates the `__init__` method for you based on the fields you declare:

```python
from dataclasses import dataclass

@dataclass
class ChunkSearchResult:
    chunk_id: str      # Python generates: self.chunk_id = chunk_id
    score: float       # Python generates: self.score = score
    child_text: str    # Python generates: self.child_text = child_text
```

The `@` symbol before `dataclass` is called a **decorator** — it's Python's way of saying "apply this transformation to the class below."

### Why not a Python dict? Why not a Django model?

**Dict problem:** `result["scroe"]` — typo, silent KeyError at runtime. `result.scroe` — typo, caught immediately by Python and your editor.

**Django model problem:** `retrieval/` must have zero Django imports. Django models carry database machinery — they connect to PostgreSQL. A `@dataclass` is pure Python with no dependencies.

### The `score` field is special

Notice `score: float` is the last field. That's intentional. The score gets updated at each pipeline stage:
- After vector search: `score = 1 - cosine_distance` (similarity)
- After BM25 search: `score = bm25_score`
- After RRF fusion: `score = rrf_combined_score`
- After re-ranking: `score = cross_encoder_score`

The same `ChunkSearchResult` object flows through all stages. Each stage replaces its score field using `dataclasses.replace()` — a built-in function that creates a copy of the object with one field changed, leaving the original untouched.

### The actual code

```python
from dataclasses import dataclass

@dataclass
class ChunkSearchResult:
    chunk_id: str         # UUID string — identifies the DocumentChunk DB row
    document_id: str      # UUID string — which document this chunk belongs to
    document_title: str   # The document's title — used for citations in Phase 4
    chunk_index: int      # Position in the document (0, 1, 2...)
    child_text: str       # Short passage (128 tokens) — what was indexed/searched
    parent_text: str      # Wide passage (512 tokens) — what the LLM reads in Phase 4
    page_number: int      # Source page — used in citations
    score: float          # Relevance score — higher is better
```

---

## Stop 2 — `retrieval/protocols.py` — The Socket Shapes

### What is it?

A file with 4 **Protocols** — abstract descriptions of what the retrieval pipeline needs, without saying where those things come from.

### Why does it exist?

The retrieval pipeline (in `retrieval/`) needs to:
- Embed a query into a vector
- Search the database for similar vectors
- Search the database using BM25
- Re-rank results

All of those real implementations live in either `documents/` (Django ORM queries) or `ingestion/` (the embedder). But `retrieval/` cannot import from Django apps.

**The solution:** `retrieval/` defines the *shape* it needs. Other modules provide objects that match that shape. Nobody crosses the boundary.

### Real-world analogy

You're a coffee machine manufacturer. Your machine needs milk. But you don't want to be locked into one milk supplier. So instead of designing your machine to accept *only* PremiumDairyCo bottles, you design it to accept *anything with a standard nozzle*.

You publish a spec: "the nozzle must be 12mm wide and push fluid when pressed." Any supplier who builds a nozzle matching that spec can plug into your machine. They never need to know about your machine's internals. You never need to know what's inside their container.

The **Protocol** is the spec sheet. The **nozzle** is the socket. The machine only knows about the socket shape — not what's on the other end.

### New Python concept: What is a `Protocol`?

In older object-oriented programming (like Java), you'd use an *interface* and every implementing class would explicitly write `implements IVectorSearch`. The implementing class knows about the interface.

Python's `Protocol` is different — it's **structural typing** (also called duck typing). If your object has the right methods with the right signatures, it satisfies the Protocol automatically. The implementing class never imports or inherits from the Protocol. It just happens to have the right shape.

```python
from typing import Protocol

class VectorSearchPort(Protocol):
    def __call__(self, embedding, document_id, k) -> list[ChunkSearchResult]: ...
```

Now any function or class that has `__call__(embedding, document_id, k)` satisfies `VectorSearchPort`. No import needed. No inheritance needed. Just the right shape.

### What is `__call__`?

In Python, `__call__` is the method that gets invoked when you call an object like a function. Every plain function has `__call__` by default.

```python
def my_function(x):     # This function has __call__ built in
    return x * 2

my_function(5)          # This calls __call__ internally
```

So by defining a Protocol with `__call__`, we're saying: *"a plain function is fine here."* `vector_search_chunks` is just a function — and it satisfies `VectorSearchPort` because it has the right `__call__` shape.

### The `...` (Ellipsis) at the end of each method

The three dots `...` (called **Ellipsis** in Python) mean "body not defined." In a Protocol, you're only describing the shape — not implementing it. It's like a job description saying "must be able to cook" without saying how the cooking should work.

### The 4 protocols and what they mean

```python
class QueryEmbedderPort(Protocol):
    def embed_single(self, text: str) -> list[float]: ...
```
*"Give me anything that converts one string into a list of numbers."*
Real implementation: `SentenceTransformerEmbedder.embed_single()` in `ingestion/embedders.py`

---

```python
class VectorSearchPort(Protocol):
    def __call__(self, embedding: list[float], document_id: uuid.UUID, k: int) -> list[ChunkSearchResult]: ...
```
*"Give me anything callable — pass it a vector, a document ID, and k — it gives me back a list of ChunkSearchResults."*
Real implementation: `vector_search_chunks()` function in `documents/selectors.py`

---

```python
class KeywordSearchPort(Protocol):
    def __call__(self, query: str, document_id: uuid.UUID, k: int) -> list[ChunkSearchResult]: ...
```
Same shape but for BM25 keyword search.
Real implementation: `keyword_search_chunks()` function in `documents/selectors.py`

---

```python
class RerankerPort(Protocol):
    def rerank(self, query: str, candidates: list[ChunkSearchResult]) -> list[ChunkSearchResult]: ...
```
*"Give me anything that has a `rerank()` method — pass it a query and a list, get back a re-ordered list."*
Real implementation: `CrossEncoderReranker.rerank()` in `retrieval/reranker.py`

### The wiring diagram

```
retrieval/protocols.py defines:      VectorSearchPort (shape)
                                              ↑
documents/selectors.py implements:   vector_search_chunks() (real function, matches shape)
                                              ↑
query/services.py wires:             pipeline = RetrievalPipeline(vector_search_fn=vector_search_chunks)
```

The pipeline only ever sees the Protocol shape. The real function is plugged in from outside.

---

## Stop 3 — `ingestion/embedders.py` — Adding `embed_single()`

### What changed and why?

In Phase 2, the embedder only had `embed_batch(texts)` — designed to embed many chunks at once during ingestion.

At search time, we need to embed ONE query string. We added `embed_single(text)` to handle this case cleanly.

### Why not just call `embed_batch([query])[0]`?

You could. It works. But it's semantically wrong — `embed_batch` implies batch processing. When you read `embed_single("what are the risks?")`, you instantly understand it embeds one thing. Clear intent = better code.

Also, `QueryEmbedderPort` requires `embed_single` — so `SentenceTransformerEmbedder` needs to have it to satisfy the protocol shape.

### The actual addition

```python
def embed_single(self, text: str) -> list[float]:
    """Embed one text string and return its vector."""
    return self.embed_batch([text])[0]
```

Three lines. It wraps `embed_batch`. All the real logic (model loading, error handling) stays in one place — `embed_batch`. No duplication.

Note: `[text]` creates a one-item list, `embed_batch` processes it, `[0]` takes the first (and only) result.

### Also updated: `EmbedderProtocol` in `ingestion/protocols.py`

The ingestion protocol also got `embed_single` added, so both the Phase 2 protocol and the Phase 3 `QueryEmbedderPort` are satisfied by the same class.

---

## Stop 4 — `retrieval/bm25.py` — Adding the `search()` Method

### What was there before?

In Phase 2, `BM25Index` could:
- `build(texts)` — create an index from a list of texts
- `serialize()` → bytes — convert to bytes for Redis storage
- `from_bytes(data)` → BM25Index — reconstruct from bytes

It could not yet *search*. The index was built but never queried.

### What was added?

A `search(query_text, k)` method that returns the top-k matching positions.

### Real-world analogy

You built a book index (like the alphabetical index at the back of a textbook). But you never actually used it to look anything up. Phase 3 adds the ability to look things up.

### What does `search()` return?

```python
def search(self, query_text: str, k: int) -> list[tuple[int, float]]:
```

It returns a list of **tuples**. Each tuple is `(corpus_position, score)`.

A **tuple** in Python is an immutable pair (or group) of values: `(5, 0.87)` means position 5, score 0.87.

`corpus_position` is the 0-based index into the original text list passed to `build()`. Since we build the BM25 index from all a document's chunks **in chunk_index order**, `corpus_position == chunk_index`. Position 0 = chunk with `chunk_index=0`. Position 5 = chunk with `chunk_index=5`.

Why not return `ChunkSearchResult` directly? Because `BM25Index` is pure Python with no Django — it can't fetch the actual text, title, or page number from the database. It only knows positions and scores. The caller (`documents/selectors.py`) maps those positions back to real database rows.

### The important edge case: BM25Okapi's negative IDF

BM25Okapi uses this formula for a term's IDF (Inverse Document Frequency):

```
IDF = log((N - df + 0.5) / (df + 0.5))
```

Where N = total documents, df = number of documents containing the term.

If a term appears in MORE than half the documents, the formula gives a **negative** number. BM25Okapi then replaces negative IDFs with `epsilon * average_idf`. If average_idf happens to be 0 (in a perfectly balanced tiny corpus), that floor is exactly 0.0.

So a term that appears in many documents might score exactly `0.0` — even though it DID appear. Our filter `score != 0.0` handles this: we keep anything non-zero (positive OR negative) and only drop chunks that scored exactly `0.0` (meaning no query term appeared in them at all).

### The actual code

```python
def search(self, query_text: str, k: int) -> list[tuple[int, float]]:
    if not query_text.strip():  # empty or whitespace-only query → return nothing
        return []

    tokens = _tokenize(query_text)                    # "Quick Fox" → ["quick", "fox"]
    raw_scores = self._index.get_scores(tokens)       # numpy array: one score per corpus position
    raw_scores = raw_scores.tolist()                  # convert numpy floats → plain Python floats

    # Drop exactly-zero scores (no query term appeared).
    # Keep negative scores (term appeared but has high document frequency).
    scored = [(pos, score) for pos, score in enumerate(raw_scores) if score != 0.0]
    scored.sort(key=lambda x: x[1], reverse=True)    # sort by score, highest first
    return scored[:k]                                 # return top k
```

New Python concepts here:
- `enumerate(raw_scores)` — takes a list and returns pairs of `(index, value)`. So `enumerate([0.5, 0.0, 0.9])` gives `(0, 0.5), (1, 0.0), (2, 0.9)`.
- `lambda x: x[1]` — a tiny anonymous function. `x` is a tuple `(pos, score)`, `x[1]` is the score. Used as the sort key.
- `reverse=True` — sort descending (highest score first).
- `[:k]` — Python slice notation. Take the first k items.

---

## Stop 5 — `documents/selectors.py` — The Database Search Functions

### What was added?

Three new functions:
1. `vector_search_chunks(embedding, document_id, k)` — searches by meaning (pgvector)
2. `keyword_search_chunks(query, document_id, k)` — searches by keywords (BM25)
3. `_get_bm25_index_or_rebuild(document_id)` — loads BM25 from Redis, rebuilds if missing

### Why here and not in `retrieval/`?

These functions touch the database — they use Django ORM (`DocumentChunk.objects.filter(...)`). Django ORM is Django. `retrieval/` cannot import Django. So the actual database queries live here, in the Django app layer, and are **passed into** the retrieval pipeline as callables that satisfy the Port protocols.

### Function 1: `vector_search_chunks`

#### How cosine distance works

Every chunk has a 384-number vector (its embedding). Your query also gets a 384-number vector. Cosine distance measures how different those two vectors are in direction.

Think of vectors as arrows pointing in space. Two arrows pointing almost the same way = similar meaning = low cosine distance. Two arrows pointing in completely different directions = different meaning = high cosine distance.

pgvector's `<=>` operator calculates this distance. The Django annotation `CosineDistance("embedding", embedding)` adds this calculation as a virtual column to each row.

#### Score conversion

pgvector returns **distance** (lower = more similar). But everywhere else in our pipeline, a **higher score = more relevant**. To be consistent, we convert:

```python
score = 1.0 - float(row.distance)
```

Cosine distance ranges from 0 to 2. So `1 - distance` gives a score roughly between -1 and 1. Higher = more relevant. Consistent with BM25 and cross-encoder conventions.

#### The actual query

```python
rows = (
    DocumentChunk.objects.filter(document_id=document_id)  # only this document
    .exclude(embedding=None)                                 # skip chunks without embeddings
    .annotate(distance=CosineDistance("embedding", embedding))  # calculate distance
    .order_by("distance")                                    # closest first
    .select_related("document")                              # fetch document title in same query
    [:k]                                                     # take top k
)
```

`select_related("document")` is Django's way of fetching the related Document row in the same SQL query (JOIN) rather than making a separate query per chunk. This avoids the "N+1 query problem" — if we fetched 10 chunks and then did 10 separate queries for each document title, that's 11 total queries. With `select_related`, it's 1.

### Function 2: `keyword_search_chunks`

1. Call `_get_bm25_index_or_rebuild(document_id)` to get the BM25 index
2. Call `bm25_index.search(query, k)` to get `(corpus_position, score)` pairs
3. Extract the chunk indices: `chunk_indices = [pos for pos, _ in position_scores]`
4. Fetch those specific `DocumentChunk` rows from DB: `DocumentChunk.objects.filter(chunk_index__in=chunk_indices)`
5. Map them back to `ChunkSearchResult` objects, preserving BM25 score order

### Function 3: `_get_bm25_index_or_rebuild`

The underscore prefix `_` means private — callers should use `keyword_search_chunks` instead of this directly.

The logic:
```
Try to load BM25 index from Redis
    → If found: deserialize and return it
    → If Redis is down: log warning, continue to rebuild
    → If not found (cache miss): continue to rebuild

Rebuild from DB:
    Load all child_text for this document, ordered by chunk_index
    Build BM25Index from those texts
    Try to save back to Redis (non-fatal if fails)
    Return the rebuilt index
```

Redis key format: `documind:bm25:{document_id}` — e.g., `documind:bm25:a1b2c3d4-...`

TTL: 7 days (604800 seconds). After 7 days Redis automatically deletes the key. Next search triggers a rebuild.

#### Production safety pattern (from project rules)

Every Redis connection in this project follows this exact pattern:
```python
r = None
try:
    r = redis_lib.from_url(settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
    # ... use r ...
finally:
    if r is not None:
        r.close()
```

- `socket_connect_timeout=2` — give up connecting after 2 seconds (don't hang forever)
- `socket_timeout=2` — give up on a read/write after 2 seconds
- `r = None` before the try — so `finally` doesn't crash if `r` was never assigned
- `r.close()` in `finally` — always release the connection, even if an exception occurred

---

## Stop 6 — `documents/services.py` — Saving BM25 to Redis

### What was added?

One new function: `save_bm25_index(document_id, bm25_index)`.

### Why here?

Because this is a **write operation** — we're saving data. By project rules (Hacksoft styleguide), all write operations live in `services.py`. Reads live in `selectors.py`.

### Why is it non-fatal?

```python
except redis_lib.RedisError as e:
    # Non-fatal: keyword search falls back to rebuilding from the DB.
    logger.warning("Failed to save BM25 index to Redis", ...)
```

If Redis is down during ingestion, we log a warning and continue. The document still gets ingested successfully. Keyword search will just rebuild the BM25 index from the database on the first search — slightly slower, but correct.

The alternative (raising an exception) would mean a Redis outage fails every document ingestion. That's too fragile.

### The TTL: why 7 days?

7 days = 604800 seconds. `r.setex(key, 604800, data)` — set with expiry.

After 7 days, Redis automatically deletes the key. This prevents Redis from filling up with stale BM25 indexes for documents that were deleted or changed. On the next search, it rebuilds from current DB data.

---

## Stop 7 — `documents/tasks.py` — The One New Line

### What changed?

One line was added after `save_document_chunks()`:

```python
save_document_chunks(document_id, result.chunks, result.embeddings)
save_bm25_index(document_id, result.bm25_index)   # ← NEW
mark_document_ready(document_id, result.chunk_count)
```

### Why was this missing in Phase 2?

In Phase 2, the ingestion pipeline built a BM25 index (`result.bm25_index`) but the Celery task never persisted it anywhere. The index was built and then thrown away at the end of the task. This was a known gap — noted in the Phase 2 comments as "Phase 3 adds Redis persistence."

This single line closes that gap. Every future document upload now automatically has its BM25 index saved to Redis.

---

## Stop 8 — `retrieval/vector_store.py` — The VectorStore Adapter

### What is it?

A class called `VectorStore` that wraps the vector search function and adds logging around it.

### Why does a wrapper exist?

The `RetrievalPipeline` could just call the search function directly. But wrapping it in a class gives us:
- **Logging at search time** — we log before and after, with the result count
- **A place to add error handling** — if the search throws, we catch and log here
- **Single Responsibility** — the pipeline orchestrates; the VectorStore handles the search concern

### Real-world analogy

Think of a TV remote control. The remote is an adapter — you press "Volume Up" and it sends the right signal to the TV. You don't wire your hand directly to the TV's circuit board. The remote is a clean wrapper.

`VectorStore` is the remote. The actual pgvector query is the TV's circuit board.

### The adapter pattern

```python
class VectorStore:
    def __init__(self, search_fn: VectorSearchPort) -> None:
        self._search_fn = search_fn              # store the injected function

    def search(self, embedding, document_id, k) -> list[ChunkSearchResult]:
        logger.debug("Vector search starting", ...)
        results = self._search_fn(embedding, document_id, k)   # delegate to injected fn
        logger.debug("Vector search returned", ...)
        return results
```

The pipeline says `self._vector_store.search(...)`. The vector store says `self._search_fn(...)`. The actual database query happens in `vector_search_chunks` in `documents/selectors.py`.

---

## Stop 9 — `retrieval/hybrid.py` — Reciprocal Rank Fusion

### What is it?

A class called `HybridFusion` that merges two ranked lists (vector search results + BM25 results) into one better ranked list.

### The problem it solves

After vector search you have: `[chunk_A, chunk_B, chunk_C]`
After BM25 search you have: `[chunk_C, chunk_D, chunk_A]`

Chunk_A appears in both lists. Chunk_C appears in both. Chunk_B only in vector. Chunk_D only in BM25.

Common sense says: chunks that multiple search methods agree on are more likely to be relevant. But how do you combine the two lists mathematically?

### RRF — Reciprocal Rank Fusion

The formula: for each chunk, sum `1 / (k + rank)` across all lists where it appears. The standard constant `k = 60`.

**Example:**
- Chunk_A: rank 1 in vector, rank 3 in BM25
  - Score = `1/(60+1)` + `1/(60+3)` = 0.01639 + 0.01587 = **0.03226**
- Chunk_C: rank 3 in vector, rank 1 in BM25
  - Score = `1/(60+3)` + `1/(60+1)` = 0.01587 + 0.01639 = **0.03226**
- Chunk_B: rank 2 in vector only (not in BM25)
  - Score = `1/(60+2)` = **0.01613**
- Chunk_D: rank 2 in BM25 only (not in vector)
  - Score = `1/(60+2)` = **0.01613**

Result: chunks that appeared in BOTH lists score ~2x higher than single-list chunks.

### Why `k = 60`?

This constant comes from the original RRF research paper (Cormack, Clarke, Buettcher 2009). It prevents top-ranked results from completely dominating. Without it, rank 1 = 1/1 = 1.0 and rank 2 = 1/2 = 0.5 — a massive gap. With k=60, rank 1 = 1/61 = 0.0164 and rank 2 = 1/62 = 0.0161 — much smoother.

### New Python concept: `dataclasses.replace()`

`ChunkSearchResult` is a dataclass. Dataclasses are immutable by default — you shouldn't change their fields directly. Instead, `replace()` creates a **copy** with one field changed:

```python
original = ChunkSearchResult(chunk_id="abc", score=0.5, ...)
updated = replace(original, score=0.03226)   # new object, original unchanged
```

This is used in `HybridFusion` to update each result's score with its RRF score.

### Handles empty lists gracefully

If keyword search returns nothing (Redis down, BM25 rebuild failed), `fuse(vector_results, [])` still works — it just returns vector_results with RRF scores applied. The pipeline never crashes.

---

## Stop 10 — `retrieval/reranker.py` — Cross-Encoder Re-Ranking

### What is it?

A class called `CrossEncoderReranker` that re-scores a shortlist of candidate chunks by reading the question AND each chunk together.

### The key difference: bi-encoder vs cross-encoder

**Bi-encoder (what you used in Phase 2 for embeddings):**
- Question → vector (separately)
- Chunk → vector (separately)
- Compare the two vectors
- Fast. Works for millions of chunks.
- Weakness: the model never saw the question and chunk together — it scored each in isolation.

**Cross-encoder (what the reranker does):**
- Feed question + chunk **together** into the model: `"[query] What are the risks? [sep] potential hazards include..."
- The model reads both at once and outputs one relevance score
- Slow. Can only run on a small number of candidates.
- Strength: much more accurate — the model understands how the question and text relate.

Think of it like:
- Bi-encoder = skimming 1000 books independently, picking the 30 that seem relevant
- Cross-encoder = carefully reading those 30 books side-by-side with your question

We only run the cross-encoder on the top 30 candidates (not all chunks), so the slowness is bounded.

### The model: `cross-encoder/ms-marco-MiniLM-L-6-v2`

- ~70MB — small and fast
- Comes from HuggingFace, downloaded automatically on first use
- Part of the `sentence-transformers` package you already have installed
- Trained on MS MARCO — Microsoft's massive Q&A dataset — so it understands relevance well

### Lazy loading — same pattern as the embedder

```python
def __init__(self, model_name=None):
    self._model = None   # NOT loaded at import time

def _load_model(self):
    if self._model is not None:
        return          # already loaded, skip
    from sentence_transformers import CrossEncoder
    self._model = CrossEncoder(self._model_name, device=device)
```

The model is only loaded when `rerank()` is first called. This avoids slowing down Django startup.

### Error handling

```python
except Exception as e:  # noqa: BLE001
    raise RerankerError(f"Cross-encoder scoring failed: {e}") from e
```

`# noqa: BLE001` is a ruff suppression comment. Ruff normally flags broad `except Exception` catches. The comment tells ruff "I know this is broad, it's intentional." This is the project rule: broad catches require this comment AND must log `error_type`.

---

## Stop 11 — `retrieval/pipeline.py` — The Orchestrator

### What is it?

A class called `RetrievalPipeline` — the conductor of the orchestra. It calls each step in order and passes results between them.

### The full sequence

```
1. embed query          → 384-dim vector
2. vector search        → top 30 candidates (k * 3)
3. keyword search       → top 30 candidates (k * 3)
4. RRF fusion           → merged top 30 list
5. cross-encoder rerank → final scored list
6. return top 10 (k)
```

### Why `candidate_multiplier = 3`?

If you want 10 final results, you fetch 30 candidates from each search first. Why?

Because vector search and BM25 each have blind spots. Vector search might miss a crucial exact-match result. BM25 might miss a semantically similar result. By fetching 30 from each (60 total, deduplicated by RRF), the cross-encoder has enough material to find the true best 10.

If you only fetched 10 from each, the cross-encoder might not even see the most relevant chunk — it might have been ranked #11 by one search method.

### Dependency injection at construction time

```python
def __init__(
    self,
    embedder: QueryEmbedderPort,        # anything with embed_single()
    vector_search_fn: VectorSearchPort, # any callable matching the Port
    keyword_search_fn: KeywordSearchPort,
    reranker: RerankerPort,             # anything with rerank()
    candidate_multiplier: int = 3,
):
```

Everything is injected. The pipeline knows nothing about where these came from. In tests, we inject fake versions. In production, we inject the real implementations.

### `VectorStore` is built inside `__init__`

```python
self._vector_store = VectorStore(search_fn=vector_search_fn)
```

The pipeline takes the raw function and wraps it in a `VectorStore`. The `keyword_search_fn` is called directly (no wrapper) because it already has Redis + DB fallback logic inside it in `documents/selectors.py`.

---

## Stop 12 — `query/serializers.py` — Request/Response Validation

### What is it?

Two serializers that validate what comes IN to the endpoint and what goes OUT.

### New concept: what is a DRF Serializer?

In Phase 2, you used serializers for the document upload. Same idea here.

A Serializer is a gatekeeper. It:
1. Receives raw data (from an HTTP request body)
2. Validates it (is `document_id` a valid UUID? is `k` between 1 and 50?)
3. Converts it to clean Python types

Think of it like a customs officer at an airport. They check your passport, look through your bags, confirm everything is valid, and then let you through in the right format.

### `SearchRequestSerializer`

```python
class SearchRequestSerializer(serializers.Serializer):
    query = serializers.CharField(min_length=1, max_length=1000)
    document_id = serializers.UUIDField()
    k = serializers.IntegerField(default=10, min_value=1, max_value=50)
```

Validates:
- `query` must be a string, 1–1000 characters
- `document_id` must be a valid UUID (not just any string)
- `k` defaults to 10, must be between 1 and 50

If any validation fails, DRF automatically returns a 400 response with a clear error message.

### `ChunkResultSerializer` + `SearchResponseSerializer`

These serialize the **outgoing** response — converting `ChunkSearchResult` dataclass objects into JSON-ready dictionaries.

---

## Stop 13 — `query/services.py` — The Composition Root

### What is it?

A function called `execute_search()` — the single place in the entire codebase that **assembles** the full retrieval pipeline from both worlds.

### What is a "composition root"?

Think of it like the electrical panel in a building. The building has lights (retrieval/), appliances (documents/), and heating (ingestion/). They all need to be wired together. The electrical panel is the one place where all the wires connect.

`query/services.py` is the electrical panel. It imports from both `retrieval/` (pure Python) and `documents/` (Django ORM) and `ingestion/` (embedder) — and wires them into a working pipeline.

This is the **only** place in the codebase that does this. That isolation is intentional.

### Local imports — why?

```python
def execute_search(query, document_id, k):
    from documents.selectors import vector_search_chunks, keyword_search_chunks  # ← inside function
    from ingestion.embedders import SentenceTransformerEmbedder                  # ← inside function
    from retrieval.pipeline import RetrievalPipeline                             # ← inside function
    from retrieval.reranker import CrossEncoderReranker                          # ← inside function
```

Imports are inside the function, not at the top of the file. This is the same pattern used in `documents/tasks.py` in Phase 2.

Why? Django apps import each other at module load time. If `query/services.py` imported `documents/selectors.py` at the top of the file, and `documents/services.py` imported something from `query/` (or something that eventually led back), you'd get a **circular import error** — Python would get stuck in a loop at startup.

Local imports break that potential loop. They only run when `execute_search()` is actually called, not at startup.

### `NoRelevantChunksError` — why 404 not 500?

```python
if not results:
    raise NoRelevantChunksError(...)  # → HTTP 404
```

A 404 means "not found." No relevant chunks = the specific content the user asked for doesn't exist in this document. That is a "not found" situation, not a server error.

A 500 would mean the server crashed. The server didn't crash — it searched successfully and found nothing. Those are completely different things.

---

## Stop 14 — `query/views.py` + `query/urls.py` — The HTTP Endpoint

### What is it?

The final piece: an HTTP view that accepts a POST request and returns search results.

### The endpoint

```
POST /api/v1/query/search/
Content-Type: application/json

{
    "query": "what are the main risks?",
    "document_id": "550e8400-e29b-41d4-a716-446655440000",
    "k": 10
}

Response 200:
{
    "query": "what are the main risks?",
    "document_id": "550e8400-...",
    "result_count": 5,
    "results": [
        {
            "chunk_id": "...",
            "document_title": "Annual Report 2024",
            "page_number": 12,
            "child_text": "potential hazards include...",
            "parent_text": "Section 4.2 Risk Factors: potential hazards...",
            "score": 0.847
        },
        ...
    ]
}
```

### The view pattern — same as Phase 2

Every view in this project follows the same 4-line pattern:
1. Validate the request with a serializer → 400 if invalid
2. Call the service function
3. Catch known exceptions → return their `http_status_code`
4. Return the response with the response serializer

```python
class SearchView(APIView):
    def post(self, request):
        # 1. Validate
        serializer = SearchRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        # 2. Call service
        try:
            results = execute_search(
                query=serializer.validated_data["query"],
                document_id=serializer.validated_data["document_id"],
                k=serializer.validated_data["k"],
            )
        # 3. Handle known errors
        except DocumentNotFoundError as e:
            return Response({"detail": str(e)}, status=e.http_status_code)  # 404
        except NoRelevantChunksError as e:
            return Response({"detail": str(e)}, status=e.http_status_code)  # 404

        # 4. Return response
        return Response({...}, status=200)
```

The view never touches the database directly. It never imports from `retrieval/`. It only calls `execute_search()` and formats the result. That's the job of a view — receive HTTP, call service, return HTTP.

### `query/urls.py` — routing

```python
urlpatterns = [
    path("query/search/", SearchView.as_view(), name="query-search"),
]
```

`core/urls.py` already had `path("api/v1/", include("query.urls"))` from Phase 1. So this registers as `POST /api/v1/query/search/` automatically.

---

## The Complete Picture

Here is how a search request flows through every file we just learned:

```
POST /api/v1/query/search/
        ↓
query/views.py (SearchView)
  → validate request (query/serializers.py)
  → call execute_search()
        ↓
query/services.py (execute_search — composition root)
  → build RetrievalPipeline with injected dependencies
        ↓
retrieval/pipeline.py (RetrievalPipeline.run)
  Step 1: embedder.embed_single(query)           → [0.12, 0.87, ...]  384 numbers
  Step 2: vector_store.search(embedding, doc_id) → top 30 chunks by meaning
  Step 3: keyword_search_fn(query, doc_id)        → top 30 chunks by keywords
  Step 4: fusion.fuse(vector, keyword)             → merged 30 by RRF score
  Step 5: reranker.rerank(query, fused[:30])       → re-scored by cross-encoder
  Step 6: return top 10
        ↓
retrieval/schemas.py (ChunkSearchResult list)
        ↓
query/views.py (formats as JSON, returns 200)
        ↓
HTTP response with ranked results
```

---

## Key Python Concepts Introduced in Phase 3

| Concept | What it is | Where used |
|---|---|---|
| `@dataclass` | Auto-generates `__init__` from field declarations | `retrieval/schemas.py` |
| `Protocol` | Describes a shape without requiring inheritance | `retrieval/protocols.py` |
| `__call__` | Makes an object callable like a function | `retrieval/protocols.py` |
| `...` (Ellipsis) | "No body" in Protocol method definitions | `retrieval/protocols.py` |
| `enumerate()` | Returns (index, value) pairs from a list | `retrieval/bm25.py` |
| `lambda` | Anonymous one-line function | `retrieval/bm25.py`, `hybrid.py` |
| `[:k]` | Slice notation — take first k items | `retrieval/bm25.py` |
| `tuple` | Immutable pair/group: `(position, score)` | `retrieval/bm25.py` |
| `dataclasses.replace()` | Create a copy with one field changed | `retrieval/hybrid.py`, `reranker.py` |
| `select_related()` | Django ORM JOIN to avoid N+1 queries | `documents/selectors.py` |
| `r = None` guard | Safe cleanup pattern for Redis connections | `documents/selectors.py`, `services.py` |
| `setex()` | Redis: set a key with an expiry time (TTL) | `documents/services.py` |
| Local imports | Imports inside a function to avoid circular chains | `query/services.py`, `documents/tasks.py` |
| Composition root | Single place that wires all dependencies together | `query/services.py` |

---

## How to Test What Was Built

### Unit tests (no Docker needed)
```bash
uv run pytest tests/unit/test_retrieval.py -v
```
18 tests covering `ChunkSearchResult`, `BM25Index.search`, `HybridFusion`, and `RetrievalPipeline`.

### Integration tests (Docker required)
```bash
docker compose up -d
uv run python manage.py migrate
uv run pytest tests/integration/test_search.py -v
```

### Live test with curl
```bash
# First upload a document
curl -X POST http://localhost:8000/api/v1/documents/ \
  -F "title=Test Doc" \
  -F "file=@your_file.pdf"

# Copy the returned document ID, then search
curl -X POST http://localhost:8000/api/v1/query/search/ \
  -H "Content-Type: application/json" \
  -d '{"query": "your question here", "document_id": "paste-id-here", "k": 5}'
```

---

## What Phase 4 Adds

Phase 3 ends at: *"here are the top 10 most relevant passages for your question."*

Phase 4 takes those passages and sends them to GPT-4o with a prompt:

```
"Given these passages:
[passage 1] [passage 2] ... [passage 10]

Answer this question: 'what are the main risks?'
Cite the page numbers where you found the information."
```

GPT-4o reads the passages and generates a natural language answer with citations. Phase 3 is the foundation — without accurate retrieval, the LLM gets wrong context and gives wrong answers.
