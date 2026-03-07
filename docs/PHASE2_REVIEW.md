# DocuMind — Pre-Phase 2 Staff Engineer Code Review

**Reviewer:** Staff Engineer (Cursor / Glean / Perplexity perspective)
**Date:** 2026-03-08
**Scope:** All Phase 1 files — every file reviewed against SOLID, Clean Architecture,
           Production Readiness, Observability, and Testability.

---

## File Grades at a Glance

| File | Grade | Reason |
|---|---|---|
| `core/settings.py` | B | Missing CONN_MAX_AGE, missing Celery time limits |
| `core/health.py` | A | Excellent: timeouts, finally-close, structured logging |
| `core/exceptions.py` | A | Clean hierarchy, http_status_code on every class |
| `core/urls.py` | A | Correct, well-commented |
| `core/asgi.py` | A | Standard |
| `core/wsgi.py` | A | Standard |
| `core/__init__.py` | C | Empty — Celery app is never loaded on startup |
| `manage.py` | A | Standard |
| `documents/models.py` | A | UUID PKs, TextChoices, db_index on status — solid |
| `documents/admin.py` | A | readonly_fields correct |
| `documents/exceptions.py` | A | Clean hierarchy |
| `documents/migrations/0001_initial.py` | B | VectorExtension first — good; no HNSW index (Phase 2 work) |
| `documents/services.py` | A | Correct stub pattern |
| `documents/selectors.py` | A | Correct stub pattern |
| `documents/tasks.py` | A | Correct empty placeholder |
| `documents/urls.py` | A | Correct empty placeholder |
| `query/exceptions.py` | A | Clean hierarchy |
| `query/services.py` | A | Correct stub |
| `query/selectors.py` | A | Correct stub |
| `query/urls.py` | A | Correct placeholder |
| `analysis/exceptions.py` | A | Clean hierarchy |
| `analysis/services.py` | A | Correct stub |
| `analysis/selectors.py` | A | Correct stub |
| `analysis/urls.py` | A | Correct placeholder |
| `ingestion/*.py` | A | Correct empty placeholders |
| `retrieval/*.py` | A | Correct empty placeholders |
| `generation/*.py` | A | Correct empty placeholders |
| `agents/*.py` | A | Correct empty placeholders |
| `pyproject.toml` | B | Dead dependency (`pydantic-settings`); ruff rules too narrow |
| `.gitignore` | C | CRITICAL: `uv.lock` is gitignored — reproducibility broken |
| `.env.example` | A | Complete, well-documented |
| `.env` | B | Debug=True and placeholder keys are fine for local dev |
| `docker-compose.yml` | B | `minio:latest` unpinned; no restart policies |
| `tests/conftest.py` | B | Minimal PDF won't be parseable by pypdf in Phase 2 |
| `tests/unit/test_models.py` | A | Well-structured, good coverage for Phase 1 |
| `tests/integration/test_health.py` | B | Uses `django.test.Client` instead of DRF `APIClient` |
| `TASKS.md` | C | Outdated — Phase 1 shown as TODO, no Phase 2 checkpoint tasks |

---

## MUST FIX — Blocks Phase 2, Fix Immediately

---

### M-1: `uv.lock` is gitignored — reproducibility is broken

**Standard violated:** Production Readiness
**File:** `.gitignore` — line 28

**The problem in plain English:**
`uv.lock` is the project's "ingredients list with exact amounts." When you write
`uv add openai`, uv records the exact version (e.g., `openai==1.35.7`) in `uv.lock`.
If `uv.lock` is gitignored, every developer and every CI run does `uv sync` and gets
*whatever is newest today* — not the version you tested with. Over time this silently
breaks the project.
This is identical to adding `package-lock.json` to `.gitignore` in a Node project.

**Exact broken code:**
```
# line 28 in .gitignore
uv.lock
```

**Exact corrected code:**
Delete line 28 entirely. The section should read:
```gitignore
# =======================================================================
# uv lock file artifacts  <- remove this comment too
# =======================================================================
                          <- remove uv.lock line
```

---

### M-2: No `core/celery.py` — Phase 2 Celery tasks will not run

**Standard violated:** Clean Architecture, Production Readiness
**Files:** `core/celery.py` (missing), `core/__init__.py` (empty)

**The problem in plain English:**
Phase 2 requires a Celery task (`documents/tasks.py`) to run the ingestion pipeline in
the background. Celery needs an "app" object to exist — like a Node.js `express` app
object. Without `core/celery.py`, running `celery -A core worker` will fail immediately.
Without the import in `core/__init__.py`, Django won't load the Celery app when the
web server starts, so scheduled tasks would silently never fire.

**Exact corrected code — create `core/celery.py`:**
```python
"""
Celery application entry point.

This file creates the Celery "app" — the engine that powers background tasks.
Think of it like creating an Express app in Node:
    const app = express()  <- that's what Celery() does here

Workers are started with:
    uv run celery -A core worker --loglevel=info
"""

import os

from celery import Celery

# Tell Celery which settings file to read (same as manage.py)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

app = Celery("documind")

# Load all CELERY_* settings from Django settings
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in every installed app's tasks.py
# This finds documents/tasks.py, query/tasks.py, etc. automatically
app.autodiscover_tasks()
```

**Exact corrected code — update `core/__init__.py`:**
```python
# Load the Celery app when Django starts.
# This ensures Celery tasks are registered before any request is handled.
from .celery import app as celery_app

__all__ = ("celery_app",)
```

---

### M-3: Missing Celery task time limits — hung tasks will block workers forever

**Standard violated:** Production Readiness
**File:** `core/settings.py` — the `# Celery` section (lines 176–184)

**The problem in plain English:**
Phase 2 ingestion tasks will parse PDFs, run embeddings, and write to the database.
If a malformed PDF causes the parser to hang, or if the OpenAI embedding API times out,
the Celery worker thread is stuck forever. With default settings, all workers can be
consumed by stuck tasks, and new documents stop processing with no error — silent failure.

Two limits work together:
- `SOFT_TIME_LIMIT`: sends a `SoftTimeLimitExceeded` exception the task can catch to
  clean up (close files, mark document as FAILED)
- `TIME_LIMIT` (hard): kills the worker process if soft limit is ignored

**Exact broken code (lines 178–184):**
```python
CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379")
CELERY_RESULT_BACKEND = env("REDIS_URL", default="redis://localhost:6379")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "UTC"
```

**Exact corrected code:**
```python
CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379")
CELERY_RESULT_BACKEND = env("REDIS_URL", default="redis://localhost:6379")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "UTC"

# Safety net: a stuck ingestion task (bad PDF, hung embedding API) will
# receive a SoftTimeLimitExceeded at 4 min so it can clean up,
# then be force-killed at 5 min.
CELERY_TASK_SOFT_TIME_LIMIT = env.int("CELERY_TASK_SOFT_TIME_LIMIT", default=240)
CELERY_TASK_TIME_LIMIT = env.int("CELERY_TASK_TIME_LIMIT", default=300)

# One task per worker slot prevents slow tasks from starving fast ones.
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
```

---

## SHOULD FIX — Tech Debt, Fix Before Phase 3

---

### S-1: Missing `CONN_MAX_AGE` — connection exhaustion risk under load

**File:** `core/settings.py` lines 107–109

**Problem:** Every HTTP request and every Celery task opens AND closes a PostgreSQL
connection. Phase 2 will have parallel Celery workers + web requests. PostgreSQL's
default max connections is 100. Under moderate load (10 workers + web traffic), the
project hits the limit and throws `OperationalError: too many connections`.

**Fix:** Add `CONN_MAX_AGE` to reuse connections across requests (Django's built-in
connection pooling):
```python
DATABASES = {
    "default": {
        **env.db("DATABASE_URL"),
        "CONN_MAX_AGE": env.int("CONN_MAX_AGE", default=60),
    }
}
```

---

### S-2: Dead dependency `pydantic-settings` in `pyproject.toml`

**File:** `pyproject.toml` line 13

**Problem:** `pydantic-settings>=2.0` is listed but never imported anywhere. The project
uses `django-environ` for all config loading. Dead dependencies increase install time,
create security surface area, and confuse future engineers.

**Fix:** Remove line 13:
```toml
"pydantic-settings>=2.0",   # DELETE THIS LINE
```

---

### S-3: `minio/minio:latest` unpinned in docker-compose.yml

**File:** `docker-compose.yml` line 50

**Problem:** MinIO releases breaking changes between major versions. `latest` today is
different from `latest` six months from now. A `docker compose pull` could silently
break the local dev environment.

**Fix:**
```yaml
image: minio/minio:RELEASE.2024-11-07T00-52-20Z   # pin to known-good version
```

---

### S-4: No `restart: unless-stopped` on docker-compose services

**File:** `docker-compose.yml`

**Problem:** If PostgreSQL crashes during a long dev session (e.g., after a Mac sleep/wake
cycle), it stays dead. Django throws `OperationalError` on every request. The developer
wonders why the app is broken and spends 10 minutes debugging before noticing the container
is stopped.

**Fix:** Add `restart: unless-stopped` to `postgres`, `redis`, and `minio` services.

---

### S-5: Hardcoded version `"0.1.0"` in `core/health.py`

**File:** `core/health.py` line 82

**Problem:** The health endpoint returns `"version": "0.1.0"` hardcoded. When the version
is bumped in `pyproject.toml`, the health endpoint will be stale. In production, ops teams
use the health endpoint to confirm which version is deployed.

**Fix:** Read version from settings or `importlib.metadata`:
```python
from importlib.metadata import version as get_version

# In the response dict:
"version": get_version("documind"),
```

---

### S-6: `tests/integration/test_health.py` uses `django.test.Client` not DRF `APIClient`

**File:** `tests/integration/test_health.py` line 9 / line 18

**Problem:** The project uses Django REST Framework. DRF adds authentication classes,
renderer negotiation, and exception handling on top of Django's raw `Client`. Using
`django.test.Client` bypasses all DRF middleware. Phase 2 API tests written with `Client`
will fail to catch auth errors that `APIClient` would catch.

**Fix:**
```python
from rest_framework.test import APIClient

def setup_method(self):
    self.client = APIClient()
```

---

### S-7: `TASKS.md` is stale — Phase 1 marked as TODO despite being complete

**File:** `TASKS.md`

**Problem:** The file says "Phase 1 Status: NOT STARTED" and all tasks are unchecked.
This is the source-of-truth task tracker. Starting Phase 2 without updating it means
the next session starts with a wrong mental model.

**Fix:** Update Phase 1 status to COMPLETE, check all Phase 1 tasks, add Phase 2
checkpoint tasks based on actual codebase structure.

---

## NICE TO HAVE — Defer

### N-1: Ruff only checks `E`, `F`, `I` — add `B` (bugbear) rules

**File:** `pyproject.toml` `[tool.ruff.lint]`

Bugbear rules catch real bugs: mutable default arguments, loop variable capture in
lambdas, `assert` in production code. Low effort, high value.
```toml
select = ["E", "F", "I", "B"]
```

---

### N-2: No request correlation ID middleware — logs can't be traced per request

**File:** `core/settings.py` `MIDDLEWARE`

When 10 concurrent requests hit the server, log lines from different requests interleave.
Without a correlation ID, you cannot reconstruct a single request's journey through the
logs in Datadog. Add `django-correlation-id` or `django-guid` before Phase 4 when LLM
calls produce many log lines per request.

---

### N-3: No test for the unhealthy path in `test_health.py`

**File:** `tests/integration/test_health.py`

The 503 response path (when PostgreSQL or Redis is down) is untested. Add a test using
`unittest.mock.patch` to simulate a DB failure and assert 503 is returned.

---

## SOLID Violations Summary

| Violation | Location | Severity |
|---|---|---|
| **SRP minor:** `health_check` handles both service probing AND HTTP response formatting | `core/health.py:29` | Low — defer to N-tier refactor |
| No other SOLID violations found in Phase 1 code | — | — |

## Clean Architecture Summary

| Check | Status |
|---|---|
| `ingestion/`, `retrieval/`, `generation/`, `agents/` have zero Django imports | PASS — all empty placeholders |
| `documents/views.py` calls services only | PASS — view is empty, correct placeholder |
| Services do write logic, selectors do read logic | PASS — stub files enforce the pattern |
| Models are Django-only, no domain logic leaking in | PASS |

## Observability Summary

| Check | Status |
|---|---|
| Every critical operation logged at correct level | PASS — `core/health.py` is exemplary |
| Log messages have `extra={}` context for Datadog filtering | PARTIAL — only health.py has `extra={}`, not enforced everywhere yet |
| Correlation ID on requests | MISSING — N-2 above |
| Structured JSON formatter for production | MISSING — noted in settings comment, deferred to Phase 4 |

## Testability Summary

| Check | Status |
|---|---|
| Unit tests run without Docker | PASS — `test_models.py` uses `@pytest.mark.django_db` which is appropriate |
| Domain code (`ingestion/`, etc.) importable without Django | PASS — all empty |
| No hidden Django imports in domain folders | PASS |
| `conftest.py` PDF fixture parseable by pypdf | FAIL — minimal PDF has no text content, will break Phase 2 parser tests |

---

## Implementation Checklist for Phase 3

After plan approval, fix in this order:

- [ ] M-1: Remove `uv.lock` from `.gitignore`
- [ ] M-2: Create `core/celery.py` + update `core/__init__.py`
- [ ] M-3: Add `CELERY_TASK_SOFT_TIME_LIMIT`, `CELERY_TASK_TIME_LIMIT`, `CELERY_WORKER_PREFETCH_MULTIPLIER` to `core/settings.py`
- [ ] Run `uv run pytest tests/ -v` — must show 0 failures
- [ ] Run `uv run ruff check .` — must show 0 errors
- [ ] Run `uv run python manage.py check` — must show 0 issues
