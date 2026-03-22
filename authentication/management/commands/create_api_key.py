"""
Management command: create a new API key and print it once.

Usage:
    uv run python manage.py create_api_key --name "local-dev"
"""

from django.core.management.base import BaseCommand

from authentication.models import APIKey


class Command(BaseCommand):
    help = "Create a new API key and print it once. The raw key is never stored."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--name",
            required=True,
            type=str,
            help="Human-readable label for this key (e.g. 'local-dev', 'ci-runner')",
        )

    def handle(self, *args, **options) -> None:
        name = options["name"]
        api_key, raw_key = APIKey.create_with_key(name=name)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"API key created: {api_key.name}"))
        self.stdout.write("")
        self.stdout.write(self.style.WARNING(f"  {raw_key}"))
        self.stdout.write("")
        self.stdout.write("Store this key securely — it will not be shown again.")
        self.stdout.write("")
