"""
WSGI configuration for DocuMind.
This is the traditional "door handle" that lets a web server (like gunicorn) open Django.
Used in production with gunicorn: gunicorn core.wsgi:application
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
application = get_wsgi_application()
