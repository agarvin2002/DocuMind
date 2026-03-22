# Retrieval System

## How It Works

The retrieval pipeline takes a query string and a document ID and returns the top-k most relevant chunks. It runs three stages in sequence:

```
Query text
  → embed query (all-MiniLM-L6-v2, 384-dim)
  → [parallel threads]
      VectorStore.search()    → top k*3 candidates  (pgvector cosine)
      BM25Index.search()      → top k*3 candidates  (Redis + BM25Okapi)
  → HybridFusion.fuse()       → deduplicated, RRF-scored list
  → CrossEncoderReranker.rerank() → top k results   (cross-attention)
```

The candidate_multiplier of 3 (k*3 per search) ensures the reranker has enough material to surface the best results. With k=5, each search stage returns 15 candidates, the fusion produces up to 30 candidates, and the reranker selects the final 5.

## Why Three Stages

Each stage addresses a known blind spot of the previous stage. This is not premature optimization — it is a deliberate response to documented failure modes.

**Vector search alone misses:**
- Exact keyword matches ("Section 4.2", specific product codes, proper names, acronyms)
- Rare terms with few training examples in the embedding model

**BM25 alone misses:**
- Semantic equivalents: "automobile" vs "car", "cardiovascular event" vs "heart attack"
- Paraphrases and synonyms
- Conceptually related text that doesn't share keywords with the query

**Fusion alone (without reranking) is not enough:**
- Vector scores (cosine distance 0.0–2.0) and BM25 scores (TF-IDF based, document-length normalized) are on incompatible scales
- RRF normalizes by rank position, not score value — it is scale-invariant
- But RRF scores query-chunk pairs independently; it has no cross-attention over the full text

**Cross-encoder alone is impractical:**
- Running a cross-encoder on thousands of chunks per query would be O(corpus size) — too slow
- The cross-encoder only runs on the shortlist (≤30 candidates), making it O(k*3) — fast

## Stage 1: Vector Search

`VectorStore.search()` queries `DocumentChunk.embedding` using pgvector's `<=>` cosine distance operator.

**Critical distinction:** pgvector's `<=>` returns **cosine distance** (0.0 = identical vectors, 2.0 = opposite vectors), not cosine similarity. Lower is better. This is the opposite of what most people expect from "similarity search."

```python
# From documents/selectors.py:
DocumentChunk.objects.filter(document_id=document_id) \
    .annotate(distance=CosineDistance("embedding", query_embedding)) \
    .order_by("distance") \
    [:candidates_k]
```

**N+1 prevention:** The query uses `select_related("document")` — document title and metadata are fetched in the same SQL join, not with separate queries per chunk.

**HNSW index:** `DocumentChunk.embedding` is indexed with HNSW (added in `documents/migrations/0002_add_hnsw_index.py` with `atomic=False`, required for `CREATE INDEX CONCURRENTLY` — a regular migration would lock the entire table). HNSW is approximate — it may miss a result that's technically within distance threshold — but the cross-encoder reranking step compensates.

## Stage 2: BM25 Keyword Search

`BM25Index` deserializes the pickled index from Redis (key: `bm25:{document_id}`) and runs BM25Okapi scoring on the query.

- Tokenizes both the query and all chunk texts with whitespace splitting (same tokenization used at index build time — a mismatch would produce wrong scores)
- Filters out zero-score results (chunks with no query term overlap)
- Returns results ordered by score descending

**Graceful degradation:** If Redis is unavailable or the key has expired, `keyword_search_chunks()` returns an empty list. `HybridFusion` handles this correctly — when one list is empty, it returns the other list with RRF scores applied to just the one non-empty list. The vector search results carry the full weight.

**Rebuilding the index:** If the 7-day TTL expires and a query arrives, the BM25 index for that document is missing from Redis. The next `ingest_document` task for that document rebuilds and re-caches it. There is currently no background rebuild — the index is rebuilt only when the document is re-ingested.

## Stage 3: Reciprocal Rank Fusion

`HybridFusion.fuse()` merges the two ranked lists using Reciprocal Rank Fusion.

**Algorithm (from `retrieval/hybrid.py`, citing the original paper):**

```
For each chunk that appears in one or more lists:
    score(chunk) = Σ  1 / (k + rank_i)
                  over all lists where chunk appears
    where k = 60  (Cormack, Clarke, Buettcher, 2009)
          rank_i = 1-based position in list i (rank 1 = best result)
```

**Why k=60:** The constant k prevents a single rank-1 result from dominating the score. With k=60, the maximum score from any single list is 1/61 ≈ 0.016. A chunk at rank 1 in both lists scores 2/61 ≈ 0.033 — exactly twice. Without k, rank-1 would score 1.0 and rank-2 would score 0.5, creating too steep a gradient.

**The fusion signal:** A chunk appearing at rank 1 in both lists scores ≈ 0.033. A chunk at rank 1 in only one list scores ≈ 0.016. Agreement between the two search methods doubles the score — this is the actual "hybrid" signal.

**Metadata source:** When a chunk appears in both lists, its metadata (text, document title, page number) is taken from the vector search result. Vector search fetches metadata via `select_related("document")` in the same query — keyword search results may not have all fields populated.

## Stage 4: Cross-Encoder Reranking

`CrossEncoderReranker.rerank()` re-scores the fused shortlist using `cross-encoder/ms-marco-MiniLM-L-6-v2`.

**Bi-encoder vs cross-encoder:**
- Bi-encoders (like all-MiniLM-L6-v2 used for embedding) encode query and chunk **separately** and compare their vectors. Fast (O(1) comparison), but the model never sees the query and chunk together.
- Cross-encoders encode the **concatenated query + chunk text** in a single forward pass. The transformer attention can model interactions between query terms and chunk terms directly. Significantly more accurate, but O(n) over the input length.

**Model details:**
- `cross-encoder/ms-marco-MiniLM-L-6-v2` (~70MB, downloaded from HuggingFace on first use)
- Trained on MS MARCO: Microsoft's large-scale passage ranking dataset (530,000 queries, 8.8M passages)
- Input: `(query, child_text)` pairs — the model scores each pair independently
- Output: a relevance score (higher = more relevant); the scale is unbounded

**Lazy loading:** The model is not loaded at import time. `_load_model()` is called on the first `rerank()` call and the model stays in memory. Device: `EMBEDDING_DEVICE` env var (default `cpu`; set `cuda` for GPU).

## K Values and Tuning

| Constant | Default | Controlled By | Effect |
|----------|---------|---------------|--------|
| `RETRIEVAL_K` | 5 | `query/constants.py` | Final chunks returned to the LLM |
| `RETRIEVAL_CANDIDATE_MULTIPLIER` | 3 | `retrieval/pipeline.py` | Each search returns `k * 3` candidates |
| `AGENT_RETRIEVAL_K` | (see `agents/constants.py`) | `agents/constants.py` | Chunks per sub-question in multi-hop |
| `AGENT_COMPARISON_K` | (see `agents/constants.py`) | `agents/constants.py` | Chunks per document in comparison/contradiction |

**Raising `RETRIEVAL_K`:** More chunks = more context for the LLM, but also more tokens and potential noise. Keep it at 5 unless you find the LLM is consistently missing information that you can see in the top-10 search results.

**Raising `RETRIEVAL_CANDIDATE_MULTIPLIER`:** More candidates for the reranker = better recall at the cost of reranking latency. The cross-encoder time scales linearly with candidate count.

## Search vs Ask

`POST /api/v1/query/search/` and `POST /api/v1/query/ask/` use the same underlying `RetrievalPipeline.run()` call. The difference is what happens after:

- **Search:** returns the ranked chunks directly as JSON — useful for building search UIs, debugging why a particular chunk was or wasn't retrieved, or evaluating retrieval quality independently of generation
- **Ask:** passes the chunks to the LLM for answer generation + SSE streaming

Use `/search/` first when debugging retrieval quality. If the right chunks are not in the top-k results, improving the answer by changing the LLM prompt won't help.
