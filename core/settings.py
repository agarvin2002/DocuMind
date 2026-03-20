"""
DocuMind Django settings.
All values are loaded from the .env file via django-environ.
"""

from pathlib import Path

import environ

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
env = environ.Env(DEBUG=(bool, False))
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(env_file)

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# ---------------------------------------------------------------------------
# Installed apps
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "rest_framework",
    "drf_spectacular",
    "storages",

    "documents",
    "query",
    "analysis",
]

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.RequestIDMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ---------------------------------------------------------------------------
# URL routing
# ---------------------------------------------------------------------------
ROOT_URLCONF = "core.urls"

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# WSGI / ASGI
# ---------------------------------------------------------------------------
WSGI_APPLICATION = "core.wsgi.application"
ASGI_APPLICATION = "core.asgi.application"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        **env.db("DATABASE_URL"),
        # Reuse DB connections across requests rather than opening a new one per request.
        # Prevents connection exhaustion under concurrent Celery + web traffic.
        "CONN_MAX_AGE": env.int("CONN_MAX_AGE", default=60),
    }
}

# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# ---------------------------------------------------------------------------
# File storage — MinIO locally, AWS S3 in production
# ---------------------------------------------------------------------------
# To switch to real AWS S3: remove AWS_S3_ENDPOINT_URL from .env.
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL", default=None)
AWS_DEFAULT_ACL = None
AWS_S3_FILE_OVERWRITE = False

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

# ---------------------------------------------------------------------------
# API documentation
# ---------------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    "TITLE": "DocuMind API",
    "DESCRIPTION": "AI-native document intelligence system",
    "VERSION": "0.1.0",
}

# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379")

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "UTC"

# A malformed PDF or hung embedding call would otherwise block a worker indefinitely.
# SOFT_TIME_LIMIT raises SoftTimeLimitExceeded so the task can mark the document FAILED
# and clean up before TIME_LIMIT force-kills the worker process.
CELERY_TASK_SOFT_TIME_LIMIT = env.int("CELERY_TASK_SOFT_TIME_LIMIT", default=600)  # 10 min
CELERY_TASK_TIME_LIMIT = env.int("CELERY_TASK_TIME_LIMIT", default=720)            # 12 min
# Default is sized for local Ollama inference (multi-hop = ~7 LLM calls × ~80s each).
# Production with GPT-4o completes in <30s — override to 300/360 via env var there.

# Prevents slow ingestion tasks from holding prefetched slots hostage.
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# Flower monitoring: workers broadcast task lifecycle events to the broker.
# Without these, Flower shows workers as online but the Tasks tab stays empty.
CELERY_WORKER_SEND_TASK_EVENTS = True
CELERY_TASK_SEND_SENT_EVENT = True

# ---------------------------------------------------------------------------
# Upload limits
# ---------------------------------------------------------------------------
DOCUMIND_MAX_UPLOAD_SIZE_MB = env.int("DOCUMIND_MAX_UPLOAD_SIZE_MB", default=50)

# ---------------------------------------------------------------------------
# LLM Generation — provider credentials
# ---------------------------------------------------------------------------
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")
OPENAI_MODEL = env("OPENAI_MODEL", default="gpt-4o")

ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
ANTHROPIC_MODEL = env("ANTHROPIC_MODEL", default="claude-sonnet-4-5")

# Bedrock uses separate credentials from the MinIO/S3 storage credentials above.
# AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY are already used for file storage (MinIO).
BEDROCK_ENABLED = env.bool("BEDROCK_ENABLED", default=False)
BEDROCK_AWS_ACCESS_KEY_ID = env("BEDROCK_AWS_ACCESS_KEY_ID", default="")
BEDROCK_AWS_SECRET_ACCESS_KEY = env("BEDROCK_AWS_SECRET_ACCESS_KEY", default="")
BEDROCK_AWS_REGION = env("BEDROCK_AWS_REGION", default="us-east-1")
BEDROCK_MODEL_ID = env("BEDROCK_MODEL_ID", default="anthropic.claude-3-sonnet-20240229-v1:0")

# Ollama — local LLM fallback, no API key needed, runs via Docker Compose
OLLAMA_ENABLED = env.bool("OLLAMA_ENABLED", default=False)
OLLAMA_BASE_URL = env("OLLAMA_BASE_URL", default="http://localhost:11434/v1")
OLLAMA_MODEL = env("OLLAMA_MODEL", default="llama3.2")

# Agent pipeline provider — selects which LLM the Phase 5 agent uses for
# structured output (classify, decompose, generate). Valid values: "ollama", "openai".
# Defaults to "ollama" when OLLAMA_ENABLED=true so local dev works without cloud keys.
# Set to "openai" to use OpenAI even while OLLAMA_ENABLED=true (e.g. running both
# Phase 4 Ollama + Phase 5 OpenAI in parallel during testing).
AGENT_LLM_PROVIDER = env("AGENT_LLM_PROVIDER", default="ollama" if env.bool("OLLAMA_ENABLED", default=False) else "openai")

# RAGAS judge provider — selects the LLM that scores eval outputs (faithfulness etc.).
# Valid values: "ollama", "openai". Same logic as AGENT_LLM_PROVIDER:
# defaults to "ollama" when OLLAMA_ENABLED=true so local dev works without cloud keys.
# Switch to "openai" once you have an OPENAI_API_KEY — scoring quality improves noticeably.
RAGAS_JUDGE_PROVIDER = env("RAGAS_JUDGE_PROVIDER", default="ollama" if env.bool("OLLAMA_ENABLED", default=False) else "openai")
# Which Ollama model to use as the RAGAS judge. Must be pulled first:
#   docker compose exec ollama ollama pull qwen2.5:3b
RAGAS_OLLAMA_MODEL = env("RAGAS_OLLAMA_MODEL", default="qwen2.5:3b")

# ---------------------------------------------------------------------------
# LLM Generation — tuning knobs
# ---------------------------------------------------------------------------
# Temperature: 0.0 = deterministic, 1.0 = creative. Low is better for RAG
# (we want consistent, grounded answers, not creative ones).
DOCUMIND_LLM_TEMPERATURE = env.float("DOCUMIND_LLM_TEMPERATURE", default=0.1)
DOCUMIND_LLM_MAX_TOKENS = env.int("DOCUMIND_LLM_MAX_TOKENS", default=1024)
DOCUMIND_LLM_TIMEOUT_SECONDS = env.float("DOCUMIND_LLM_TIMEOUT_SECONDS", default=30.0)
# Agent pipeline timeout — higher than streaming timeout because agent LLM calls are
# non-streaming and local Ollama inference can take 60-200s per call on consumer hardware.
# 800 tokens ÷ 5 tok/s (llama3.2:3b) = 160s per call → 200s gives safe headroom.
# Production OpenAI: 800 tokens ÷ 200 tok/s = 4s — this limit is never reached.
AGENT_LLM_TIMEOUT_SECONDS = env.float("AGENT_LLM_TIMEOUT_SECONDS", default=200.0)
# Max tokens of document context sent to the LLM. Chunks are trimmed if over this limit.
DOCUMIND_MAX_CONTEXT_TOKENS = env.int("DOCUMIND_MAX_CONTEXT_TOKENS", default=6000)

# ---------------------------------------------------------------------------
# LangSmith — LLM observability (no-op when LANGCHAIN_TRACING_V2=false)
# ---------------------------------------------------------------------------
LANGCHAIN_TRACING_V2 = env.bool("LANGCHAIN_TRACING_V2", default=False)
LANGCHAIN_API_KEY = env("LANGCHAIN_API_KEY", default="")
LANGCHAIN_PROJECT = env("LANGCHAIN_PROJECT", default="documind")

# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True

# ---------------------------------------------------------------------------
# Default primary key field type
# ---------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
# LOG_FORMAT controls output format:
#   "verbose" (default) → human-readable text for local development
#   "json"              → structured JSON for Datadog/CloudWatch in production
#
# Every log line is automatically stamped with request_id via RequestIDFilter.
# Set LOG_FORMAT=json in staging/production .env.

LOG_FORMAT = env("LOG_FORMAT", default="verbose")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,

    "filters": {
        "request_id": {
            "()": "core.middleware.RequestIDFilter",
        },
    },

    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} [{request_id}] - {message}",
            "style": "{",
            "datefmt": "%Y-%m-%dT%H:%M:%S",
        },
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "fmt": "%(asctime)s %(levelname)s %(name)s %(request_id)s %(message)s",
            "rename_fields": {
                "asctime": "timestamp",
                "levelname": "level",
                "name": "logger",
            },
            "static_fields": {"service": "documind"},
            "datefmt": "%Y-%m-%dT%H:%M:%SZ",
        },
    },

    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": LOG_FORMAT,
            "filters": ["request_id"],
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs" / "documind.log",
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 5,
            "formatter": LOG_FORMAT,
            "filters": ["request_id"],
        },
    },

    "loggers": {
        "": {
            "handlers": ["console", "file"],
            "level": env("LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}
