# Import the Celery app so Django loads it when the server starts.
# Without this line, tasks defined in tasks.py files are not registered
# until a worker is explicitly started — which causes silent failures in
# any code that calls .delay() or .apply_async() from the web process.
from .celery import app as celery_app

__all__ = ("celery_app",)
