# Agent Pipeline

## Why an Agent

The streaming ask endpoint (`/query/ask/`) is excellent for direct questions: "What does Section 3 say about liability?" But some questions require multi-step reasoning that a single retrieve-then-generate pass cannot handle:

| Question | Why Direct Q&A Fails |
|---------|---------------------|
| "What are the risks, opportunities, and timeline in this document?" | Needs decomposition — one retrieval with "risks opportunities timeline" as the query produces noisy, unfocused results |
| "Compare the liability clauses in document A and document B" | Needs retrieval from two separate documents simultaneously |
| "Do Section 2 and Section 5 contradict each other?" | Needs a contradiction detection prompt, not a factual Q&A prompt |
| "Summarize all the key decisions mentioned throughout the document" | Needs multi-hop retrieval across sections |

A LangGraph state machine handles all four patterns with typed routing, shared state, and a consistent error contract — without duplicating retrieval or generation logic.

## The Four Workflow Types

**`simple`** — Single retrieve + generate pass. Used when `classify_query_node` determines the question is direct and doesn't require decomposition. Same logic as `/query/ask/` but synchronous (no streaming) and routed through the agent job system.

Example: "What is the effective date of this contract?"

**`multi_hop`** — The question is decomposed into N sub-questions (typically 2–5). Each sub-question is retrieved independently. Each retrieval produces a sub-answer. All sub-answers are synthesized into a final answer.

Example: "What are the key risks, the main mitigations, and the projected timeline?"
→ Decomposed into: ["What are the key risks?", "What mitigations are described?", "What is the projected timeline?"]
→ 3 retrievals → 3 sub-answers → 1 synthesized final answer

**`comparison`** — Retrieval runs in sequence across all `document_ids` in the request. All chunks from all documents are pooled. A single comparison-specific prompt generates a structured comparison answer.

Example (2 documents): "How do these two contracts differ on indemnification?"
→ Retrieve from doc_A (AGENT_COMPARISON_K chunks) + doc_B (AGENT_COMPARISON_K chunks) → comparison generation

**`contradiction`** — Same retrieval pattern as comparison. The generation prompt explicitly instructs the LLM to identify and report contradictions and conflicts between the retrieved passages.

Example: "Are there any contradictions between these two policy versions?"

## State Machine

All four workflow types share the same `AgentState` TypedDict. Nodes read from it and return partial dicts with only the fields they modify. LangGraph merges each node's return dict into the shared state.

```
START
  │
  ▼
classify_query_node
  ├── sets workflow_type, complexity
  │
  ├─[error]──────────────────────────────────────────────────────► error_node ─► END
  │
  ├─[simple]────────────────────────────────────────────────────► simple_passthrough_node ─► END
  │
  ├─[comparison]────────────────────────────────────────────────► comparison_retrieve_node
  │                                                                      │
  │                                                                      ▼
  │                                                              comparison_generate_node ─► END
  │
  ├─[contradiction]─────────────────────────────────────────────► contradiction_retrieve_node
  │                                                                      │
  │                                                                      ▼
  │                                                             contradiction_detect_node ─► END
  │
  └─[multi_hop]─────────────────────────────────────────────────► plan_query_node
                                                                         │
                                                              ┌─[error]──┘
                                                              │
                                                              ▼
                                                   retrieve_for_subquestion_node
                                                              │
                                                   ┌─[error]──┘
                                                              │
                                                              ▼
                                                   generate_sub_answers_node
                                                              │
                                                   ┌─[error]──┘
                                                              │
                                                              ▼
                                                        synthesize_node ─► END

[error_node is always ─► END]
```

## Error Handling Contract

This is the single most important rule in the agent codebase.

**Nodes NEVER raise exceptions to the LangGraph graph engine.**

If an unhandled exception escapes a node function, LangGraph terminates the graph run with an error. The `AnalysisJob` stays in `RUNNING` status forever — it never transitions to `FAILED`, and the polling endpoint returns `{"status": "running"}` indefinitely.

The contract:
```python
def some_node(state: AgentState, *, dep: SomeDep) -> dict:
    try:
        result = dep.do_work(state["question"])
        return {"some_field": result}
    except SomeExpectedError as exc:
        logger.error("some_node_failed", extra={"job_id": state["job_id"], "error": str(exc)})
        return {"error": str(exc)}  # ← set error, return normally
```

Every routing function checks `state.get("error")` before deciding the next node:
```python
def _route_after_plan(state: AgentState) -> str:
    return "error_node" if state.get("error") else "retrieve_for_subquestion_node"
```

`error_node` formats a user-facing message and ensures the result dict is structurally complete:
```python
def error_node(state: AgentState) -> dict:
    error_msg = state.get("error") or "Unknown agent error"
    return {"final_answer": f"Analysis failed: {error_msg}", "citations": []}
```

The `result_data` written to `AnalysisJob` always has the same shape — `final_answer`, `sub_questions`, `sub_answers`, `citations`, `error`. Clients can always deserialize the result without conditional logic.

## Async Execution Model

```
POST /api/v1/analysis/
  │   {question, document_ids, workflow_type}
  │
  ├── validate: all document_ids exist and status=READY
  ├── AnalysisJob.objects.create(status=PENDING, input_data={...})
  ├── run_analysis_task.delay(str(job_id))        [Celery dispatch]
  └── return 202 Accepted {id, status: "pending", workflow_type}

GET /api/v1/analysis/{job_id}/
  ├── Redis GET result:{job_id}  → return if hit (completed jobs cached)
  └── AnalysisJob.objects.get(id=job_id) → return current state

Celery: run_analysis_task(job_id)
  ├── mark_job_running(job_id)
  ├── _get_executor().run(job)    [LangGraph state machine]
  ├── mark_job_complete(job_id, result_data)
  └── cache in Redis: SET result:{job_id} result_data [24h TTL]
```

**Status polling:** The `GET` endpoint first checks Redis. Completed jobs are cached with a 24-hour TTL, so most polls after completion are Redis lookups (sub-millisecond). The PostgreSQL fallback handles the first few polls before the result is cached, and any cache misses after TTL expiry.

**Recommended polling interval:** 2-5 seconds. Multi-hop workflows with local Ollama can take 60-300 seconds.

## Query Planner

`QueryPlanner` uses `StructuredLLMClient` (backed by Instructor) to classify and decompose queries:

**`classify(question, document_ids) → ComplexityClassification`:**
Returns a Pydantic model with `workflow_type` (simple/multi_hop/comparison/contradiction), `complexity` (simple/complex), and `reasoning`. The workflow_type overrides what the user specified in the request — the classifier may determine a `multi_hop` request is actually `simple` and fast-path it.

**`decompose(question, n) → QueryDecomposition`:**
Returns a Pydantic model with a `sub_questions` list (up to `AGENT_SUB_QUESTION_MAX` questions). The sub-questions are designed to be independently answerable and collectively sufficient to address the original question.

Both results are cached in Redis. Repeated identical questions (same text, same document scope) skip the LLM classification call entirely.

**On failure:** Both `classify()` and `decompose()` raise `PlanningError` if the LLM call fails (timeout, network error, Pydantic validation error). `classify_query_node` and `plan_query_node` in `graph.py` each catch `PlanningError`, set `state["error"]`, and return normally — the graph then routes to `error_node`, and the `AnalysisJob` ends with `status=failed`. This follows the [Error Handling Contract](#error-handling-contract): nodes never raise to the graph engine.

## Dependency Injection

`build_agent_graph(planner, retrieval_tool, gen_tool)` uses `functools.partial` to bind all dependencies into each node function:

```python
graph.add_node(
    "classify_query_node",
    partial(classify_query_node, planner=planner)
)
```

Node functions are pure Python functions — no module-level globals, no `settings` imports inside node bodies. All I/O goes through the injected dependencies. This makes individual nodes independently testable:

```python
def test_classify_query_node_simple_question():
    fake_planner = FakeQueryPlanner(workflow_type="simple")
    state = AgentState(question="What is the title?", ...)
    result = classify_query_node(state, planner=fake_planner)
    assert result["workflow_type"] == "simple"
```

The compiled graph is cached as a module-level singleton per Celery worker process via `_get_executor()` with double-checked locking. `StateGraph.compile()` validates all edges and nodes — this runs once per process startup, not per job.

## Result Format

All four workflow types produce a `result_data` dict with the same shape. Fields not applicable to the workflow type are empty:

**`simple` workflow result:**
```json
{
  "workflow_type": "simple",
  "question": "What is the effective date?",
  "final_answer": "The agreement is effective as of January 1, 2024.",
  "sub_questions": [],
  "sub_answers": [],
  "citations": [{"document_title": "Contract.pdf", "page_number": 1, "chunk_id": "..."}],
  "error": null
}
```

**`multi_hop` workflow result:**
```json
{
  "workflow_type": "multi_hop",
  "question": "What are the key risks, mitigations, and timeline?",
  "final_answer": "The primary risks are... The mitigations include... The timeline runs from...",
  "sub_questions": ["What are the key risks?", "What mitigations are described?", "What is the timeline?"],
  "sub_answers": ["The key risks are...", "The mitigations include...", "The timeline is..."],
  "citations": [{"document_title": "Report.pdf", "page_number": 3, ...}, ...],
  "error": null
}
```

**`comparison` workflow result:**
```json
{
  "workflow_type": "comparison",
  "question": "How do these contracts differ on indemnification?",
  "final_answer": "Contract A requires... while Contract B limits...",
  "sub_questions": [],
  "sub_answers": [],
  "citations": [
    {"document_title": "ContractA.pdf", "page_number": 7, ...},
    {"document_title": "ContractB.pdf", "page_number": 5, ...}
  ],
  "error": null
}
```

**Failed job result:**
```json
{
  "workflow_type": "multi_hop",
  "question": "...",
  "final_answer": "Analysis failed: LLM provider timeout after 200s",
  "sub_questions": [],
  "sub_answers": [],
  "citations": [],
  "error": "LLM provider timeout after 200s"
}
```

## Adding a New Workflow Type

1. **Add to `AnalysisJob.WorkflowType`** in `analysis/models.py`:
   ```python
   class WorkflowType(models.TextChoices):
       ...
       SUMMARIZATION = "summarization", "Multi-Section Summarization"
   ```

2. **Create the migration:** `uv run python manage.py makemigrations`

3. **Add nodes** in `agents/graph.py` following the error-contract pattern (nodes catch exceptions, set `state["error"]`, return normally)

4. **Register nodes** in `build_agent_graph()` with `functools.partial`

5. **Add routing branch** in `_route_after_classify()`:
   ```python
   routes = {
       ...
       AnalysisJob.WorkflowType.SUMMARIZATION: "summarization_retrieve_node",
   }
   ```

6. **Add the prompt key** in `generation/prompts.py`

7. **Add edges** in `build_agent_graph()` for the new nodes

8. **Add tests** in `tests/unit/test_agent_graph.py` — test each new node function with `FakeRetrievalTool` and `FakeStructuredLLMClient`

No changes to the HTTP layer (`analysis/views.py`, `analysis/serializers.py`) — the new workflow type appears automatically in the `workflow_type` field choices.
