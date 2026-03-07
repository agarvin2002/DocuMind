#!/usr/bin/env python
"""
Django's command-line utility — the master remote control.

Usage examples:
  uv run python manage.py runserver      → start the web server
  uv run python manage.py migrate        → apply database changes
  uv run python manage.py createsuperuser → create an admin user
  uv run python manage.py shell          → open a Python shell with Django loaded
"""

import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Make sure it's installed and you're using "
            "'uv run python manage.py' instead of plain 'python manage.py'."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
