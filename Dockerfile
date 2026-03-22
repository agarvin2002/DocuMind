# =============================================================================
# Stage 1: builder — install all production dependencies into a virtualenv
# =============================================================================
FROM python:3.12-slim AS builder

# Copy uv binary directly from the official image — no pip install needed
COPY --from=ghcr.io/astral-sh/uv:0.6 /uv /usr/local/bin/uv

# Enable bytecode compilation and use copy mode for the venv
# (copy mode avoids hardlinked files that break in multi-stage builds)
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Install dependencies first — this layer is cached as long as pyproject.toml
# and uv.lock don't change, even if application code changes
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy the application code and do the final sync (installs the project itself)
COPY . .
RUN uv sync --frozen --no-dev


# =============================================================================
# Stage 2: final — lean runtime image with no build tools
# =============================================================================
FROM python:3.12-slim

# Create a non-root user — running as root in a container is a security risk
RUN useradd --uid 1000 --no-create-home --shell /bin/false documind

WORKDIR /app

# Copy only the virtualenv from the builder stage — no uv, no build tools
COPY --from=builder --chown=documind:documind /app/.venv /app/.venv
COPY --from=builder --chown=documind:documind /app /app

# Put the virtualenv's bin directory first in PATH so `python` and `gunicorn`
# resolve to the venv without needing to activate it
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER documind

EXPOSE 8000

# gunicorn is the production WSGI server — never use `manage.py runserver` in production.
# Workers=4 is a safe default for a CPU-bound workload on a 2-core machine.
# Override GUNICORN_WORKERS at runtime for larger instances.
CMD ["gunicorn", "core.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
