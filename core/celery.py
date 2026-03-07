"""
Celery application entry point.

Creates the shared Celery app used by all background tasks (ingestion,
embedding generation, etc.). Start a worker with:
    uv run celery -A core worker --loglevel=info
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

app = Celery("documind")

# Load CELERY_* settings from Django settings (CELERY_BROKER_URL, CELERY_TASK_TIME_LIMIT, etc.)
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks.py in every installed app.
app.autodiscover_tasks()
