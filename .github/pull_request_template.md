## What and Why
<!-- What does this PR do and why is it needed? One or two sentences.
     For bug fixes: describe the root cause, not just the symptom.
     For features: describe the problem being solved, not the solution. -->


## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Refactor / clean-up
- [ ] Performance improvement
- [ ] Docs / comments
- [ ] CI / tooling / infra

## Changes Made
<!-- Bullet list of the meaningful changes. Skip files changed for obvious reasons.
     Focus on decisions: why this approach over alternatives, what tradeoffs were made. -->

-

## Testing Done
<!-- What did you test and how? Describe happy path + at least one edge case.
     For retrieval changes: include before/after search quality observations if relevant.
     For agent changes: describe which workflow types were exercised. -->


## Checklist

**Code quality**
- [ ] `uv run pytest tests/unit/` passes locally
- [ ] `uv run ruff check .` returns no errors
- [ ] New code has corresponding unit tests using fakes, not `unittest.mock.patch`

**Architecture rules**
- [ ] No Django imports inside `ingestion/`, `retrieval/`, `generation/`, or `agents/`
- [ ] New dependencies injected via constructor — not imported as module-level globals inside functions
- [ ] New LLM-calling code uses the existing `LLMProviderPort` / `StructuredLLMPort` — no direct SDK calls in views or tasks

**Agent pipeline (skip if not touching `agents/`)**
- [ ] Node functions catch all exceptions, set `state["error"]`, and return normally — no unhandled raises
- [ ] New routing functions check `state.get("error")` before choosing the next node

**HTTP layer (skip if not adding/changing endpoints)**
- [ ] New endpoints have a `ThrottleClass` applied
- [ ] New endpoints return `{"detail": "..."}` for all error responses via the existing exception hierarchy
- [ ] Rate limit constant added to `core/constants.py` if a new throttle tier was needed

**Data layer (skip if not touching models)**
- [ ] Migrations generated and committed (`uv run python manage.py makemigrations --check` passes)
- [ ] New `VectorField` columns have an HNSW migration with `atomic = False`

**Security**
- [ ] No secrets, API keys, or credentials in code or comments
- [ ] User-supplied input is validated by a serializer before reaching service or pipeline code
- [ ] File uploads validated for type and size before storage

## Breaking Changes
<!-- Does this change the API contract, database schema, Redis key format, or SSE event format?
     If yes: describe what breaks, who is affected, and the migration path.
     If no: delete this section. -->
