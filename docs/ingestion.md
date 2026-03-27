# Ingestion Pipeline

## How It Works

When a user uploads a document via `POST /api/v1/documents/`, Django saves the file to MinIO (or S3 in production) and creates a `Document` row with `status=PENDING`. It immediately dispatches a Celery task — the HTTP response returns before any processing happens.

```
POST /api/v1/documents/ {title, file}
  → save file to MinIO/S3
  → Document.objects.create(status=PENDING)
  → ingest_document.delay(str(document_id))
  → return 201 Created {id, status: "pending"}
```

The Celery worker (`documents/tasks.py`) picks up the task, opens the file from storage, and hands it to `IngestionPipeline.run()`. The pipeline is a **pure transformation** — it receives a file-like object and returns a `PipelineResult` dataclass. It has no Django imports, no database calls, no file I/O of its own. The task layer owns all side effects.

```
Celery: ingest_document(document_id)
  → mark_document_processing(document_id)     [Document.status = PROCESSING]
  → StorageClient().download_file()           [open file from MinIO/S3]
  → IngestionPipeline.run(file_obj, file_type)
      ├── parser.parse(file_obj)              → [(page_num, text), ...]
      ├── chunker.chunk(pages)                → [ChunkData, ...]
      ├── embedder.embed_batch(child_texts)   → [[float, ...], ...]
      └── BM25Index.build(child_texts)        → BM25Index
  → save_document_chunks(document_id, chunks, embeddings)  [PostgreSQL + pgvector]
  → save_bm25_index(document_id, bm25_index)               [Redis]
  → mark_document_ready(document_id, chunk_count)          [Document.status = READY]
```

## Document Status Lifecycle

```
PENDING      File saved to storage, Celery task dispatched.
             API consumers should wait before querying.

PROCESSING   Celery task has started. Do not poll more than once per second.

READY        All chunks embedded and indexed. The document can be queried.
             DocumentChunk rows exist in PostgreSQL.
             BM25 index exists in Redis.

FAILED       Pipeline raised an exception. Document.error_message is set.
             Check error_message for the failure reason.
             The document will not transition out of FAILED automatically.
```

Poll `GET /api/v1/documents/{id}/` until `status` is `ready` or `failed`. Typical ingestion time: 5-30 seconds depending on document size and whether the embedding model is already loaded in memory.

## Parsing

`get_parser(file_type)` dispatches by file extension. PDF parsing uses `pypdf` — text is extracted page by page, with the 1-indexed page number tracked per token so each chunk knows which page it came from.

**Supported file types:**
- `.pdf` — `pypdf` (included)

**Adding a new file type** (e.g., DOCX):
1. Implement a class with `parse(file_obj) -> list[tuple[int, str]]` (list of `(page_number, text)` tuples)
2. Register it in `ingestion/parsers.py`: add `".docx": DocxParser()` to the dispatch dict
3. No other changes needed — `IngestionPipeline` calls `get_parser(file_type)` generically

**Upload limit:** `DOCUMIND_MAX_UPLOAD_SIZE_MB` env var (default 50MB). Enforced by DRF before the file reaches the ingestion pipeline.

**Image-only and partially scanned PDFs:** `pypdf` can only extract text from PDFs with an embedded text layer. For scanned documents (images of pages with no text layer), `pypdf` returns empty strings per page. Single unreadable pages are skipped with a `WARNING` log and do not abort ingestion — the remaining pages are still processed. If the entire document produces no text chunks after parsing (fully image-only or encrypted), the pipeline transitions the document to `status=failed` with `error_message: "Document produced no text chunks — file may be image-only or empty"`. There is no OCR fallback in the current implementation.

## Hierarchical Chunking

This is the most important design decision in the ingestion pipeline.

**The problem:** Embedding a 512-token window means the vector represents the average of 512 tokens of content — precision suffers, especially for precise questions about specific facts. But sending a 128-token window to the LLM loses the surrounding context needed for a good answer.

**The solution:** Use two different windows for two different purposes.

```
                    child (128 tokens) — embedded and indexed
                    ┌──────────────────────────────────────────┐
...────────────────────────────────────────────────────────────────────────...
                ┌────────────────────────────────────────────────────────┐
                    parent (512 tokens, centered on child) — sent to LLM
```

**Exact parameters** (from `ingestion/chunkers.py`):
- `CHILD_TOKENS = 128` — window size for embedding and retrieval
- `PARENT_TOKENS = 512` — window size for LLM context
- `OVERLAP_TOKENS = 20` — overlap between adjacent child windows (prevents boundary artifacts)

**Step size:** `CHILD_TOKENS - OVERLAP_TOKENS = 108` tokens. Adjacent child windows share 20 tokens.

**Parent window centering:** The parent window is centered on the child window start position, then clamped to document boundaries:
```python
parent_start = max(0, child_start - PARENT_TOKENS // 2)
parent_end   = min(len(all_tokens), child_start + CHILD_TOKENS + PARENT_TOKENS // 2)
```

**Tokenization:** Whitespace splitting (`text.split()`). Deterministic, dependency-free, CPU-only. No tiktoken or sentencepiece dependency. Tradeoff: no stopword removal or stemming — retrieval quality is compensated by the BM25 + vector hybrid approach.

**Output:** Each `ChunkData` contains `chunk_index`, `child_text`, `parent_text`, and `page_number` (the page where the child window starts). The `chunk_index` is sequential across the entire document.

## Embedding

`SentenceTransformerEmbedder` wraps `sentence-transformers` with `all-MiniLM-L6-v2`:
- **384-dimensional** float vectors
- **Batched:** all child texts from one document are embedded in a single `embed_batch()` call — one model inference pass, not one per chunk
- **Lazy-loaded:** the model is not loaded at import time. It loads on the first `embed_batch()` call and stays in memory for the lifetime of the worker process
- **Device:** `EMBEDDING_DEVICE` env var (default `cpu`; set to `cuda` if a GPU is available)

The embeddings are stored as `VectorField(dimensions=384)` on each `DocumentChunk.embedding`. pgvector's HNSW index on this field enables fast approximate nearest-neighbor search at query time.

## BM25 Index

After embedding, `BM25Index.build(child_texts)` constructs a keyword search index from all child texts in the document:
- Uses the `rank-bm25` library (BM25Okapi algorithm)
- Tokenizes with the same whitespace split as the chunker (identical tokenization at build and query time is essential)
- Serialized with `pickle` and stored in Redis at key `bm25:{document_id}` with a 7-day TTL

At retrieval time, the index is deserialized from Redis (~10ms for a typical document). If Redis is unavailable or the key has expired, the [retrieval pipeline falls back gracefully](retrieval.md#stage-2-bm25-keyword-search) — it returns an empty keyword result list and vector search carries the full weight for that request (no error is raised).

**TTL expiry and rebuild:** The Redis key expires after 7 days. There is no background rebuild — the index is rebuilt only when the document is re-ingested via a new `ingest_document` Celery task. To force a rebuild without re-uploading the file, use the Django shell snippet in the [Debugging section](#debugging-a-failed-ingestion):
```python
mark_document_pending(document_id)
ingest_document.delay(str(document_id))
```

**Why Redis:** The BM25 index is a serialized in-memory data structure, not relational data. Redis is the right store — fast serialization, automatic TTL, no schema needed.

## Celery Task Design Decisions

Three explicit decisions in `documents/tasks.py`:

**`max_retries=0`:** A corrupt PDF retried 3 times is still corrupt. Retrying unparseable documents would mislead users about progress. Fail fast, set `error_message`, and surface the problem immediately.

**`CELERY_TASK_SOFT_TIME_LIMIT`:** The soft time limit (default 600s) raises `SoftTimeLimitExceeded` inside the task. The task catches this, calls `mark_document_failed(document_id, "Ingestion timed out after 4 minutes")`, and exits cleanly. The hard kill at `CELERY_TASK_TIME_LIMIT` (default 720s) is the safety net — the task should have exited cleanly before this fires.

**`CELERY_WORKER_PREFETCH_MULTIPLIER=1`:** With the default of 4, a Celery worker prefetches 4 tasks. If one ingestion takes 10 minutes and the worker prefetched 3 others, those 3 tasks sit idle. With prefetch=1, each worker slot processes one task at a time — slow ingestion jobs don't block other work.

## Debugging a Failed Ingestion

**Via API:**
```bash
curl -H "X-API-Key: dm_xxxx" http://localhost:8000/api/v1/documents/{doc_id}/
# → {"status": "failed", "error_message": "Document produced no text chunks — file may be image-only or empty"}
```

**Via Django admin:** `/admin/documents/document/` — filter by status=failed, click the document to see `error_message`.

**Via Celery logs:** Every log line from the ingestion task includes `document_id` in structured fields. Find the task's log lines with:
```bash
# If using json logging:
grep '"document_id": "your-doc-uuid"' logs/app.log

# Or watch Flower dashboard at http://localhost:5555 — click the failed task to see its traceback
```

**Re-triggering ingestion manually** (Django shell):
```python
from documents.tasks import ingest_document
from documents.services import mark_document_pending

mark_document_pending(document_id)
ingest_document.delay(str(document_id))
```
