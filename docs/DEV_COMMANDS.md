# DocuMind — Development Commands

## IMPORTANT

This file contains the ONLY correct commands to run this project.
Never guess commands. If a command is not here, ask before running anything.

All commands are run from the project root directory:
/Users/pando-agarvin/projects/DocuMind

---

## Prerequisites (Install Once)

### 1. Install uv (Python package manager)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
Verify it works:
```bash
uv --version
```

### 2. Install Docker Desktop
Download from: https://www.docker.com/products/docker-desktop
After install, verify:
```bash
docker --version
docker compose version
```

---

## Project Setup (Run Once, First Time Only)

### Step 1: Initialize the Python environment
```bash
uv sync
```
This reads pyproject.toml and installs all dependencies.

### Step 2: Create your .env file
```bash
cp .env.example .env
```
Then open .env and fill in your API keys (see PROJECT_CONTEXT.md for what is needed).

### Step 3: Start infrastructure
```bash
docker compose up -d
```
This starts PostgreSQL (with pgvector) and Redis in the background.
The `-d` flag means "detached" — runs in background, terminal stays usable.

### Step 4: Run database migrations
```bash
uv run python manage.py migrate
```
This reads all migration files in each Django app and creates the database
tables. You must run this every time you change a model.

### Step 5: Verify everything is running
```bash
docker compose ps
```
All three services should show status "running".

---

## Daily Development (Every Session)

### Start infrastructure (if not already running)
```bash
docker compose up -d
```

### Start the Django development server
```bash
uv run python manage.py runserver
```
- Auto-reloads when you save any Python file
- Keep this terminal open while developing
- Stop with Ctrl+C

### Start the background worker (open a NEW terminal tab)
```bash
uv run celery -A core worker --loglevel=info
```
- Required for document processing to work (uploads are processed in background)
- Keep this terminal open
- Stop with Ctrl+C

### Open API documentation
```bash
open http://localhost:8000/api/docs/
```
Interactive page to test every API endpoint visually.

### Open Django admin panel
```bash
open http://localhost:8000/admin/
```
A built-in web interface to view and manage all data in the database.
Login with the superuser account you create below.

---

## Django-Specific Commands

### Create a superuser (for Django admin panel)
```bash
uv run python manage.py createsuperuser
```
Follow the prompts to set a username, email, and password.
Use this to log into http://localhost:8000/admin/

### Open the Django shell (Python console with full app loaded)
```bash
uv run python manage.py shell
```
Useful for testing queries and debugging models interactively.

### Check for any code errors before running
```bash
uv run python manage.py check
```
Django will report any configuration problems.

---

## Stopping Everything

### Stop the Django development server
Press `Ctrl+C` in the terminal running runserver.

### Stop the Celery worker
Press `Ctrl+C` in the terminal running celery.

### Stop Docker infrastructure
```bash
docker compose down
```
This stops the containers but KEEPS your data.

### Stop Docker AND delete all data (use carefully)
```bash
docker compose down -v
```
WARNING: This deletes all data in PostgreSQL, Qdrant, and Redis.
Only use this if you want a completely clean reset.

---

## Installing New Dependencies

### Add a production dependency
```bash
uv add <package-name>
```
Example:
```bash
uv add anthropic
```

### Add a development-only dependency
```bash
uv add --dev <package-name>
```
Example:
```bash
uv add --dev pytest
```

### Never use pip directly
Always use `uv add` — not `pip install`. Using pip bypasses uv's
dependency management and causes problems.

---

## Database Commands

### Create new migration files (after changing models.py)
```bash
uv run python manage.py makemigrations
```
Run this every time you add or change a field in any models.py file.
Django compares your models to the existing migrations and generates
a new migration file describing what changed.

### Apply all pending migrations to the database
```bash
uv run python manage.py migrate
```
Run this after makemigrations to actually apply the changes to PostgreSQL.

### See all migrations and their status
```bash
uv run python manage.py showmigrations
```
Shows which migrations have been applied ([X]) and which are pending ([ ]).

### Roll back the last migration (undo)
```bash
uv run python manage.py migrate documents 0001
```
Replace "documents" with the app name and "0001" with the migration to roll back to.

---

## Testing

### Run all tests
```bash
uv run pytest
```

### Run tests with output printed (useful for debugging)
```bash
uv run pytest -s
```

### Run a specific test file
```bash
uv run pytest tests/unit/test_chunkers.py
```

### Run tests with coverage report
```bash
uv run pytest --cov=src/documind
```

---

## Evaluation

### Run the full evaluation pipeline
```bash
uv run python tests/evals/run_evals.py
```

### Run the retrieval benchmark
```bash
uv run python scripts/benchmark.py
```

---

## Ingestion Scripts

### Load sample documents for testing
```bash
uv run python scripts/ingest_demo.py
```

---

## Checking Service Health

### Check if all containers are running
```bash
docker compose ps
```

### Check API health
```bash
curl http://localhost:8000/api/health/
```
Expected response: `{"status": "ok", "version": "0.1.0"}`

### Check pgvector extension is installed in PostgreSQL
```bash
docker compose exec postgres psql -U documind -d documind -c "SELECT * FROM pg_extension WHERE extname = 'vector';"
```
Expected response: one row showing the vector extension is installed.

### Check PostgreSQL is running
```bash
docker compose exec postgres pg_isready
```
Expected response: `/var/run/postgresql:5432 - accepting connections`

### Check Redis is running
```bash
docker compose exec redis redis-cli ping
```
Expected response: `PONG`

### Check Flower dashboard is running
```bash
curl -u admin:admin http://localhost:5555/healthcheck
```
Expected response: `{"status": "OK"}`

---

## Viewing Logs

### View all container logs
```bash
docker compose logs
```

### Follow logs in real time (streaming)
```bash
docker compose logs -f
```

### View logs for a specific service
```bash
docker compose logs postgres
docker compose logs redis
docker compose logs flower
docker compose logs minio
```

### View recent API logs
The API server logs print directly in the terminal where uvicorn is running.

---

## LangSmith (LLM Observability)

### Access LangSmith dashboard
Open in browser: https://smith.langchain.com

All LLM calls are automatically traced when these are set in .env:
```
LANGCHAIN_API_KEY=your-key
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=documind
```

---

## Common Problems and Solutions

### "Port already in use" when starting API
Another process is using port 8000. Kill it:
```bash
lsof -ti:8000 | xargs kill -9
```

### "Cannot connect to Docker daemon"
Docker Desktop is not running. Open Docker Desktop app and wait for it to start.

### "Module not found" errors
Dependencies are not installed. Run:
```bash
uv sync
```

### Database connection refused
PostgreSQL container is not running. Start it:
```bash
docker compose up -d postgres
```

### "uv: command not found"
uv is not installed or not in PATH. Install it:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.zshrc
```

### Environment variable missing error
You have not set up .env correctly. Check:
```bash
cat .env
```
Compare with .env.example and fill in any missing values.

---

## Service URLs (Local Development)

| Service | URL | Purpose |
|---------|-----|---------|
| API | http://localhost:8000/api/ | Main API |
| API Docs | http://localhost:8000/api/docs/ | Interactive Swagger documentation |
| Django Admin | http://localhost:8000/admin/ | Database browser — view all data including embeddings |
| Flower | http://localhost:5555 | Celery task monitoring — real-time task status, worker health, queue depth |
| LangSmith | https://smith.langchain.com | LLM trace viewer |

---

## Git Commands

### See what files have changed
```bash
git status
```

### Stage all changed files
```bash
git add .
```

### Commit with a message
```bash
git commit -m "Phase 1 complete: project foundation"
```

### Push to GitHub
```bash
git push origin main
```

### NEVER commit these files
- .env (contains secrets)
- __pycache__/ (Python cache, auto-generated)
- .venv/ (virtual environment, auto-generated)

These are in .gitignore and will be excluded automatically.
