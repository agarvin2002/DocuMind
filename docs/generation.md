# Generation & Streaming

## The Ask Endpoint End-to-End

`POST /api/v1/query/ask/` streams an LLM-generated answer as Server-Sent Events (SSE). Here is the complete flow from request to stream complete:

```
POST /api/v1/query/ask/ {query, document_id, k?, model?}
  │
  ├── Pre-flight validation (errors here → normal HTTP response, no stream)
  │     get_document_by_id(document_id)     → 404 if not found
  │     _resolve_provider(model)            → 400 if model not configured
  │
  ├── SemanticCache.lookup(query, document_id)
  │     → HIT:  yield build_sse_token_event(cached_answer)
  │             yield build_sse_citations_event(cached_citations)
  │             yield build_sse_done_event()  → RETURN
  │     → MISS: continue
  │
  ├── RetrievalPipeline.run(query, document_id, k)  → top-k chunks
  │     → 404 if no chunks found
  │
  ├── get_system_prompt() + build_user_message(query, chunks)
  │
  ├── FallbackLLMClient.stream(system, user, temperature, max_tokens, timeout)
  │     for each token:
  │       accumulated += token
  │       yield build_sse_token_event(token)
  │
  ├── _resolve_citations(accumulated, chunks)
  │     → regex [1][2]... → chunk metadata
  │
  ├── yield build_sse_citations_event(citations)
  ├── yield build_sse_done_event()
  └── SemanticCache.store(query, document_id, {answer, citations})
```

## SSE Wire Protocol

This is the canonical wire format. Any client consuming the `/ask/` endpoint must handle all four event types.

```
# Token events — one per LLM token, repeated throughout the stream
data: <token text>\n\n

# Citations event — sent exactly once, after the last token
event: citations
data: [{"chunk_id": "...", "document_title": "...", "page_number": 3, "quote": "..."}]\n\n

# Done event — client should close the EventSource / ReadableStream
event: done
data: [DONE]\n\n

# Error event — only for mid-stream failures (headers already sent)
event: error
data: <error message>\n\n
```

**Important distinction:** Pre-stream errors (document not found, model not configured) return standard HTTP error responses (`{"detail": "..."}`) with the appropriate status code. The SSE `error` event is only used for failures that occur **after the stream has started** — because HTTP status and headers are already sent, the error must be communicated inside the event stream itself.

## Streaming Response Headers

`execute_ask()` is a generator that yields SSE strings. The Django view wraps it in `StreamingHttpResponse`:

```python
response = StreamingHttpResponse(
    execute_ask(query, document_id, k, model),
    content_type="text/event-stream",
)
response["Cache-Control"] = "no-cache"
response["X-Accel-Buffering"] = "no"
```

Two headers beyond `content_type` are required for correct behavior:
- `Cache-Control: no-cache` — prevents CDN caches from holding the stream
- `X-Accel-Buffering: no` — disables nginx's default response buffering. Without this header, nginx holds the entire response body in memory before forwarding it to the client. The user sees nothing until the LLM finishes generating — which completely defeats the purpose of streaming.

## LLM Provider Architecture

`LLMProviderPort` is a structural `Protocol` (Python `typing.Protocol` with `@runtime_checkable`):

```python
class LLMProviderPort(Protocol):
    def stream(
        self,
        system_prompt: str,
        user_message: str,
        *,
        temperature: float,
        max_tokens: int,
        timeout: float,
    ) -> Iterator[str]: ...
```

Any class with a matching `stream()` method satisfies this protocol — no `isinstance` check needed at runtime, no inheritance required. This means a `FakeLLMProvider` in tests satisfies the protocol simply by implementing `stream()`.

**Four concrete providers** (all in `generation/llm.py`):

| Provider | Class | Authentication | Notes |
|----------|-------|---------------|-------|
| OpenAI | `OpenAIProvider` | `OPENAI_API_KEY` | Uses `openai.OpenAI` SDK |
| Anthropic | `AnthropicProvider` | `ANTHROPIC_API_KEY` | Uses Anthropic native SDK |
| AWS Bedrock | `BedrockProvider` | `BEDROCK_AWS_*` credentials | Claude models via `AnthropicBedrock`; data stays in AWS VPC |
| Ollama | `OllamaProvider` | None (local) | OpenAI-compatible API at `OLLAMA_BASE_URL`; no real API key |

All four are decorated with `@traceable(name="...", run_type="llm")` — LangSmith captures full span data when `LANGCHAIN_TRACING_V2=true`. When tracing is disabled, `@traceable` is a no-op.

## Fallback Chain

`FallbackLLMClient` implements the Chain of Responsibility pattern:

```python
class FallbackLLMClient:
    def __init__(self, providers: list[LLMProviderPort]) -> None:
        self._providers = providers  # ordered list — tries each in sequence

    def stream(self, system_prompt, user_message, *, ...) -> Iterator[str]:
        for i, provider in enumerate(self._providers):
            try:
                yield from provider.stream(...)
                return  # success — stop trying
            except AnswerGenerationError as exc:
                log warning with provider name and error
                # continue to next provider
        raise AnswerGenerationError("All providers failed")
```

The providers list is built at the composition root (`query/services.py`) from whichever providers are configured in `.env`. The configured order: OpenAI → Anthropic → Bedrock → Ollama.

**Zero-change extensibility:** Adding a new provider requires:
1. Implement a class with `stream(system_prompt, user_message, *, temperature, max_tokens, timeout) -> Iterator[str]`
2. Add it to the `providers` list in `query/services.py`

No changes to `FallbackLLMClient`. No changes to any view or service. The protocol is structural — your class satisfies it automatically.

## Citation Extraction

The system prompt instructs the LLM to cite sources inline using `[1]`, `[2]` style markers. After the stream completes, `_resolve_citations()` maps markers to chunk metadata:

```python
markers = re.findall(r"\[(\d+)\]", accumulated_answer)
for marker in markers:
    idx = int(marker) - 1  # [1] → index 0
    chunk = chunks[idx]
    citations.append(Citation(
        chunk_id=str(chunk.chunk_id),
        document_title=chunk.document_title,
        page_number=chunk.page_number,
        quote=chunk.parent_text[:CITATION_QUOTE_MAX_CHARS],
    ))
```

Citations are deduplicated — the same chunk cited twice appears once. If a marker references an out-of-range index (e.g., the LLM hallucinates `[99]` when there are only 5 chunks), that marker is silently skipped. A warning is logged if markers exist in the answer but no citations can be resolved.

## Structured Output (Agent Pipeline Only)

The streaming path uses `FallbackLLMClient.stream()` → raw tokens. The agent pipeline uses a **separate** path: `StructuredLLMClient` backed by the Instructor library.

`StructuredLLMClient.complete(system_prompt, user_message, response_model, ...)` returns a validated Pydantic model instance — not a string. This is used for:
- `QueryPlanner.classify()` → returns `ComplexityClassification` (workflow_type, complexity, reasoning)
- `QueryPlanner.decompose()` → returns `QueryDecomposition` (sub_questions list, reasoning)

**`max_retries=0`:** Instructor has a built-in retry mechanism that re-calls the LLM if validation fails. With a local Ollama model that takes 60-200s per call, even one retry doubles latency. `max_retries=0` is set explicitly to disable this.

## Prompt Architecture

All prompts are externalized in `generation/prompts.py` with a key-based lookup:

```python
from generation.prompts import get_system_prompt, get_agent_prompt, build_user_message

system_prompt = get_system_prompt()           # for /ask/ streaming
agent_prompt  = get_agent_prompt("sub_answer") # for agent pipeline
user_message  = build_user_message(query, chunks, max_context_tokens=6000)
```

**Agent prompt keys:**
- `"complexity_classifier"` — classifies query into simple/multi_hop/comparison/contradiction
- `"query_decomposition"` — decomposes a question into N sub-questions
- `"sub_answer"` — answers a single sub-question given retrieved chunks
- `"comparison"` — generates a structured comparison answer from multiple document chunks
- `"contradiction_detection"` — detects and reports contradictions across document chunks

Modifying a prompt: edit the string in `generation/prompts.py`. No other changes needed.

## Tuning Parameters

| Env Var | Default | When to Change |
|---------|---------|---------------|
| `DOCUMIND_LLM_TEMPERATURE` | `0.1` | Low (≤0.2) for RAG — consistent, factual answers. Raise to 0.5–0.7 for creative summarization tasks. |
| `DOCUMIND_LLM_MAX_TOKENS` | `1024` | Raise if answers are getting cut off mid-sentence. Lower if you want shorter answers to save costs. |
| `DOCUMIND_LLM_TIMEOUT_SECONDS` | `90.0` | Fine for cloud providers (OpenAI/Anthropic typically respond in <5s). Keep at 90 for local Ollama. |
| `AGENT_LLM_TIMEOUT_SECONDS` | `200.0` | Agent uses non-streaming calls which are slower. Local Ollama can take 60-200s per call on consumer hardware. |
| `DOCUMIND_MAX_CONTEXT_TOKENS` | `6000` | Total token budget for all retrieved chunks. Chunks are trimmed if this limit is exceeded. Raise if the LLM supports longer context and you want more coverage. |
