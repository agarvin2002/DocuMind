## Description
<!-- What does this PR do, and why? -->

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Refactor / clean-up
- [ ] Docs / comments
- [ ] CI / tooling / infra

## Testing Done
<!-- Describe what you tested and how. For new features, list the happy path and edge cases verified. -->

## Checklist
- [ ] `uv run pytest tests/unit/` passes locally
- [ ] `uv run ruff check .` returns no errors
- [ ] No Django imports in `ingestion/`, `retrieval/`, `generation/`, or `agents/`
- [ ] No hardcoded secrets, API keys, or magic numbers
- [ ] Comments follow the public-repo comment standards (no analogies, no tutorial prose)
- [ ] Migrations created and tested if models changed (`uv run python manage.py makemigrations --check`)
