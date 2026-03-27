# API Reference

## Authentication

All endpoints except `/health/` require an API key.

**Header:** `X-API-Key: <key>`

**Key format:** `dm_<32-char-urlsafe-base64>` — for example, `dm_abc123XYZ...`

**Generating a key:**
```bash
uv run python manage.py create_api_key dev-key
# Output: API key created: dm_aBcDeF...  (shown once — never stored again)
```

The raw key is printed exactly once. Only a SHA-256 hash is stored in the database — if a key is lost, create a new one and deactivate the old one via Django admin (`/admin/authentication/apikey/`).

**If auth fails:**
```json
HTTP 401 — {"detail": "Authentication credentials were not provided."}
HTTP 403 — {"detail": "API key has been revoked."}
```

---

## Rate Limits

All limits are per API key, per 60-second sliding window. The window is enforced with an atomic Redis Lua script — no race conditions, no double-counting.

| Endpoint | Limit | Why |
|----------|-------|-----|
| `POST /api/v1/documents/` | 30 req/min | S3 upload + Celery task dispatch |
| `POST /api/v1/query/search/` | 60 req/min | Retrieval only — no LLM call |
| `POST /api/v1/query/ask/` | 20 req/min | LLM generation + streaming |
| `POST /api/v1/analysis/` | 10 req/min | Agent pipeline — expensive multi-hop reasoning |

**429 response:**
```
HTTP 429
Retry-After: 34

{"detail": "Request was throttled. Expected available in 34 seconds."}
```

The `Retry-After` header tells clients exactly how many seconds to wait.

**Fail-open:** If Redis is unavailable, rate limiting is disabled for that request — availability beats strict enforcement.

---

## Error Response Format

All errors use the same shape:

```json
{"detail": "<human-readable message>"}
```

| Status | Meaning |
|--------|---------|
| 400 | Validation error — check request body |
| 401 | Missing or malformed API key |
| 403 | Valid key format but key has been revoked |
| 404 | Resource not found (document, job) |
| 422 | Semantic error — e.g., document not ready for querying |
| 429 | Rate limit exceeded |
| 500 | Unexpected server error |
| 503 | Service unavailable (dependency down) or model not configured |

**Pre-stream vs mid-stream errors for `/ask/`:** Errors detected before the stream starts (404, 503) return a normal HTTP error response. Errors occurring after tokens have started streaming use an `event: error` SSE event because HTTP status and headers are already sent.

---

## POST /api/v1/documents/

Upload a document and queue it for ingestion.

**Request:** `multipart/form-data`

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `file` | File | Yes | PDF only, max 50 MB (configurable via `DOCUMIND_MAX_UPLOAD_SIZE_MB`) |
| `title` | String | No | Max 500 chars. Defaults to the filename stem if omitted. |

```bash
curl -X POST http://localhost:8000/api/v1/documents/ \
  -H "X-API-Key: dm_xxxx" \
  -F "title=Q3 Risk Report" \
  -F "file=@/path/to/report.pdf"
```

**Response: `201 Created`**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "title": "Q3 Risk Report",
  "original_filename": "report.pdf",
  "file_type": ".pdf",
  "file_size": 204800,
  "status": "pending",
  "error_message": null,
  "chunk_count": null,
  "created_at": "2026-03-22T10:00:00Z",
  "updated_at": "2026-03-22T10:00:00Z"
}
```

**After upload:** The document is `pending`. Ingestion runs asynchronously in Celery. Poll `GET /api/v1/documents/{id}/` until `status` is `ready` or `failed`. Typical wait: 5–30 seconds depending on file size and whether the embedding model is already loaded.

**Errors:**
- `400` — unsupported file type or file exceeds size limit
- `400` — missing `file` field

---

## GET /api/v1/documents/{document_id}/

Poll document ingestion status and retrieve metadata.

```bash
curl -H "X-API-Key: dm_xxxx" \
  http://localhost:8000/api/v1/documents/3fa85f64-5717-4562-b3fc-2c963f66afa6/
```

**Response: `200 OK`**

Status `pending` or `processing` (ingestion in progress):
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "title": "Q3 Risk Report",
  "original_filename": "report.pdf",
  "file_type": ".pdf",
  "file_size": 204800,
  "status": "processing",
  "error_message": null,
  "chunk_count": null,
  "created_at": "2026-03-22T10:00:00Z",
  "updated_at": "2026-03-22T10:00:05Z"
}
```

Status `ready` (document can be queried):
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "title": "Q3 Risk Report",
  "original_filename": "report.pdf",
  "file_type": ".pdf",
  "file_size": 204800,
  "status": "ready",
  "error_message": null,
  "chunk_count": 47,
  "created_at": "2026-03-22T10:00:00Z",
  "updated_at": "2026-03-22T10:00:18Z"
}
```

Status `failed` (ingestion error):
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "title": "Q3 Risk Report",
  "original_filename": "report.pdf",
  "file_type": ".pdf",
  "file_size": 204800,
  "status": "failed",
  "error_message": "Document produced no text chunks — file may be image-only or empty",
  "chunk_count": null,
  "created_at": "2026-03-22T10:00:00Z",
  "updated_at": "2026-03-22T10:00:12Z"
}
```

**Status meanings:**

| Status | Meaning | Next action |
|--------|---------|-------------|
| `pending` | File saved, Celery task not yet picked up | Keep polling |
| `processing` | Celery task is running | Keep polling (max once per second) |
| `ready` | All chunks indexed — document is queryable | Stop polling, proceed to search/ask |
| `failed` | Ingestion failed | Read `error_message`, re-upload if fixable |

**Errors:**
- `404` — document ID not found

---

## POST /api/v1/query/search/

Run the full retrieval pipeline and return ranked text chunks. Use this to debug retrieval quality independently of generation.

**Request:** `application/json`

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `query` | String | Yes | 1–1000 chars |
| `document_id` | UUID | Yes | Must exist with `status=ready` |
| `k` | Integer | No | 1–50, default 10 |

```bash
curl -X POST http://localhost:8000/api/v1/query/search/ \
  -H "X-API-Key: dm_xxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "what are the main risks?",
    "document_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "k": 5
  }'
```

**Response: `200 OK`**
```json
{
  "query": "what are the main risks?",
  "document_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "result_count": 5,
  "results": [
    {
      "chunk_id": "a1b2c3d4-...",
      "document_title": "Q3 Risk Report",
      "page_number": 3,
      "child_text": "The primary operational risk is vendor concentration...",
      "parent_text": "Section 2 — Risk Assessment. The primary operational risk is vendor concentration across three suppliers who account for 70% of component volume. A disruption to any one supplier would delay production by 8–12 weeks...",
      "score": 0.0327
    }
  ]
}
```

**Response fields:**

| Field | Description |
|-------|-------------|
| `chunk_id` | UUID of the specific chunk — use to trace back to the source document |
| `child_text` | The 128-token window that was embedded and matched against the query |
| `parent_text` | The 512-token window that will be sent to the LLM if `/ask/` is called — includes surrounding context |
| `score` | RRF fusion score (higher = more relevant, but only meaningful for relative ranking) |

**Tip:** If the chunks in the top results do not contain the information you expected, improving the LLM prompt will not help — the retrieval pipeline is returning wrong chunks. Tune `k` or the query phrasing instead.

**Errors:**
- `400` — invalid request body
- `404` — document not found
- `422` — no relevant chunks found for the query

---

## POST /api/v1/query/ask/

Stream a grounded LLM answer as Server-Sent Events (SSE).

**Request:** `application/json`

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `query` | String | Yes | 1–1000 chars |
| `document_id` | UUID | Yes | Must exist with `status=ready` |
| `k` | Integer | No | 1–20, default 5 |
| `model` | String | No | Model identifier — omit to use the fallback chain (OpenAI → Anthropic → Bedrock → Ollama; see [Generation docs](generation.md#fallback-chain)) |

```bash
curl -X POST http://localhost:8000/api/v1/query/ask/ \
  -H "X-API-Key: dm_xxxx" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  --no-buffer \
  -d '{
    "query": "what are the main risks?",
    "document_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
  }'
```

**Model values (optional):**

| Provider | Example value |
|----------|---------------|
| OpenAI | `"gpt-4o"` |
| Anthropic | `"claude-sonnet-4-6-20251001"` |
| AWS Bedrock | `"anthropic.claude-3-sonnet-20240229-v1:0"` |
| Ollama | `"qwen2.5:3b"`, `"llama3.2"` |
| Auto-fallback | omit field or send `null` |

**SSE Response:** `200 OK`, `Content-Type: text/event-stream`

The response is a stream of four event types. A client must handle all four:

```
# Token events — one per LLM token, repeated until the answer is complete
data: The primary operational risk [1] is vendor concentration

data:  across three key suppliers.

# Citations event — sent exactly once, after the last token
event: citations
data: [{"chunk_id":"a1b2c3d4-...","document_title":"Q3 Risk Report","page_number":3,"quote":"The primary operational risk is vendor concentration..."}]

# Done event — client should close the connection
event: done
data: [DONE]

# Error event — only if a failure occurs after streaming has started
event: error
data: LLM provider timeout after 90s
```

**Reading the stream in JavaScript:**

With `EventSource` (GET only — not compatible with POST):
```javascript
// Use fetch + ReadableStream for POST endpoints:
const response = await fetch('/api/v1/query/ask/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'dm_xxxx',
    'Accept': 'text/event-stream',
  },
  body: JSON.stringify({ query: 'what are the main risks?', document_id: '...' }),
});

const reader = response.body.getReader();
const decoder = new TextDecoder();
let buffer = '';

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, { stream: true });
  const lines = buffer.split('\n\n');
  buffer = lines.pop(); // incomplete chunk back to buffer

  for (const block of lines) {
    if (block.startsWith('event: citations')) {
      const data = block.split('\ndata: ')[1];
      const citations = JSON.parse(data);
      // handle citations
    } else if (block.startsWith('event: done')) {
      reader.cancel();
      break;
    } else if (block.startsWith('data: ')) {
      const token = block.slice(6); // strip "data: "
      // append token to answer display
    }
  }
}
```

**Pre-stream errors** (returned before any SSE events — normal HTTP responses):

| Scenario | Status | Body |
|----------|--------|------|
| Document not found | 404 | `{"detail": "Document not found"}` |
| Document not ready | 422 | `{"detail": "Document is not ready for querying"}` |
| Model not configured | 503 | `{"detail": "Model 'gpt-4o' is not available — OPENAI_API_KEY not set"}` |

**Cache behavior:** Before running retrieval, the server checks the semantic cache. If a semantically equivalent question (cosine distance ≤ 0.08) was asked for the same document within the past 7 days, the cached answer is streamed immediately — zero LLM cost.

---

## POST /api/v1/analysis/

Create an async agent analysis job. Returns immediately with a job ID. Poll the status endpoint until complete.

Use this for questions that require multi-step reasoning or comparison across multiple documents — questions that the single-pass `/ask/` endpoint cannot handle well.

**Request:** `application/json`

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `question` | String | Yes | 1–2000 chars |
| `document_ids` | Array of UUIDs | Yes | 1–10 UUIDs, all must exist with `status=ready` |
| `workflow_type` | String | No | `simple`, `multi_hop`, `comparison`, `contradiction`. Defaults to `multi_hop`. |

```bash
curl -X POST http://localhost:8000/api/v1/analysis/ \
  -H "X-API-Key: dm_xxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the key risks, the mitigations described, and the projected timeline?",
    "document_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
    "workflow_type": "multi_hop"
  }'
```

**When to use each workflow type:**

| Type | Use when | Example |
|------|----------|---------|
| `simple` | Direct factual question, same as `/ask/` but routed through the agent system | "What is the effective date?" |
| `multi_hop` | Question with multiple distinct sub-topics requiring separate retrieval | "What are the risks, mitigations, and timeline?" |
| `comparison` | Comparing content across two or more documents | "How do Contract A and Contract B differ on liability?" |
| `contradiction` | Finding conflicts within or between documents | "Are there any contradictions between these two policy versions?" |

**Note:** The LLM classifier always determines the final `workflow_type`, regardless of what you specified. It may downgrade a `multi_hop` request to `simple` (fast-path) **or** upgrade a `simple` request if the question is more complex than it appears. The `result_data.workflow_type` in the completed job shows what actually ran. Bypassing classification is not currently supported. See the [Agent Pipeline docs](agent-pipeline.md#query-planner) for how the classifier works.

The [four workflow types](agent-pipeline.md#the-four-workflow-types) are described in the agent pipeline docs.

**Response: `202 Accepted`**
```json
{
  "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "workflow_type": "multi_hop",
  "status": "pending",
  "input_data": {
    "question": "What are the key risks, the mitigations described, and the projected timeline?",
    "document_ids": ["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
    "workflow_type": "multi_hop"
  },
  "result_data": null,
  "error_message": null,
  "started_at": null,
  "completed_at": null,
  "created_at": "2026-03-22T10:05:00Z"
}
```

**Errors:**
- `400` — validation error (invalid `workflow_type`, `document_ids` empty, etc.)
- `404` — one or more document IDs not found

---

## GET /api/v1/analysis/{job_id}/

Poll an analysis job for its current status and result.

```bash
curl -H "X-API-Key: dm_xxxx" \
  http://localhost:8000/api/v1/analysis/7c9e6679-7425-40de-944b-e07fc1f90ae7/
```

**Polling strategy:** Check every 2–5 seconds. Multi-hop workflows with local Ollama can take 60–300 seconds. Completed jobs are cached in Redis for 24 hours — most polls after completion return in under 1 ms.

**Response while running (`status: "pending"` or `"running"`):**
```json
{
  "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "workflow_type": "multi_hop",
  "status": "running",
  "input_data": {...},
  "result_data": null,
  "error_message": null,
  "started_at": "2026-03-22T10:05:02Z",
  "completed_at": null,
  "created_at": "2026-03-22T10:05:00Z"
}
```

**Response on success (`status: "complete"`):**
```json
{
  "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "workflow_type": "multi_hop",
  "status": "complete",
  "input_data": {...},
  "result_data": {
    "workflow_type": "multi_hop",
    "question": "What are the key risks, the mitigations described, and the projected timeline?",
    "final_answer": "The primary risks are vendor concentration and regulatory uncertainty [1]. The mitigations described include dual-sourcing agreements and a dedicated compliance team [2]. The timeline runs from Q1 2026 through Q4 2027 [3].",
    "sub_questions": [
      "What are the key risks?",
      "What mitigations are described?",
      "What is the projected timeline?"
    ],
    "sub_answers": [
      "The key risks are vendor concentration (70% of components from 3 suppliers) and regulatory uncertainty in the EU market.",
      "Mitigations include dual-sourcing agreements signed with two backup suppliers and a dedicated compliance team of 4 FTEs.",
      "The timeline runs from Q1 2026 (risk assessment complete) through Q4 2027 (full market entry)."
    ],
    "citations": [
      {"document_title": "Q3 Risk Report", "page_number": 3, "chunk_id": "a1b2c3d4-..."},
      {"document_title": "Q3 Risk Report", "page_number": 5, "chunk_id": "b2c3d4e5-..."},
      {"document_title": "Q3 Risk Report", "page_number": 8, "chunk_id": "c3d4e5f6-..."}
    ],
    "error": null
  },
  "error_message": null,
  "started_at": "2026-03-22T10:05:02Z",
  "completed_at": "2026-03-22T10:05:47Z",
  "created_at": "2026-03-22T10:05:00Z"
}
```

**Response on failure (`status: "failed"`):**
```json
{
  "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "workflow_type": "multi_hop",
  "status": "failed",
  "input_data": {...},
  "result_data": {
    "workflow_type": "multi_hop",
    "question": "...",
    "final_answer": "Analysis failed: LLM provider timeout after 200s",
    "sub_questions": [],
    "sub_answers": [],
    "citations": [],
    "error": "LLM provider timeout after 200s"
  },
  "error_message": "LLM provider timeout after 200s",
  "started_at": "2026-03-22T10:05:02Z",
  "completed_at": "2026-03-22T10:08:22Z",
  "created_at": "2026-03-22T10:05:00Z"
}
```

`result_data` always has the same structure regardless of failure — `final_answer`, `sub_questions`, `sub_answers`, `citations`, `error`. No conditional logic needed on the client side.

**Errors:**
- `404` — job ID not found

---

## GET /api/v1/health/

Check service health. No authentication required. Used for load balancer readiness probes.

**What is checked:** PostgreSQL (`SELECT 1`) and Redis (`PING`). **What is not checked:** MinIO and Ollama. A `healthy` response does not guarantee file uploads or LLM calls will succeed — those services fail with their own specific errors at request time.

```bash
curl http://localhost:8000/api/v1/health/
```

**Response: `200 OK` (all dependencies reachable):**
```json
{
  "status": "healthy",
  "checks": {
    "postgres": "ok",
    "redis": "ok"
  },
  "version": "0.1.0"
}
```

**Response: `503 Service Unavailable` (any dependency down):**
```json
{
  "status": "unhealthy",
  "checks": {
    "postgres": "ok",
    "redis": "error: Connection refused"
  },
  "version": "0.1.0"
}
```

