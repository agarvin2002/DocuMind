"""
ASGI configuration for DocuMind.
ASGI is the modern door handle — it supports async features like streaming responses.
We use this for streaming LLM output back to the user in real time.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
application = get_asgi_application()
