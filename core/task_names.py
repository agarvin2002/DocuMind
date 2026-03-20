"""
core/task_names.py — Typed constants for every registered Celery task name.

Celery task names default to their Python module path. If a task module is
moved or renamed without updating callers that reference the task by string
(e.g. apply_async, admin actions, monitoring dashboards), those callers break
silently with no import error.

Centralising task names here means a rename is a single-file change with a
compile-time error at every callsite, rather than a runtime surprise.

Usage:
    from core.task_names import INGEST_DOCUMENT
    celery_app.send_task(INGEST_DOCUMENT, args=[str(document_id)])
"""

# documents app tasks
INGEST_DOCUMENT: str = "documents.tasks.ingest_document"

# analysis app tasks
RUN_ANALYSIS_JOB: str = "analysis.tasks.run_analysis_job"
