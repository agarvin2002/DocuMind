#!/bin/sh
# Pre-push hook: lint + unit tests must pass before any push lands.
# Install: sh scripts/install-hooks.sh
set -e

echo "▶ ruff check ..."
uv run ruff check .

echo "▶ ruff format --check ..."
uv run ruff format --check .

echo "▶ pytest tests/unit/ ..."
uv run pytest tests/unit/ -q

echo "✓ All pre-push checks passed."
