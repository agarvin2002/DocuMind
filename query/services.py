"""
query/services.py — Composition root for retrieval and generation pipelines.

This is the single place in the codebase that wires together:
    - retrieval/ (pure Python — no Django)
    - generation/ (pure Python — no Django)
    - documents/ (Django ORM queries)
    - ingestion/ (embedder)

All provider/pipeline imports are local to their factory functions to avoid
circular import chains at module load time (query → documents → models → apps → query).

Usage:
    from query.services import execute_search, execute_ask
    results = execute_search(query="...", document_id=uuid, k=10)
    for sse_event in execute_ask(query="...", document_id=uuid, k=5):
        yield sse_event
"""

import logging
import re
import threading
import time
import uuid
from collections.abc import Iterator

from query.exceptions import ModelNotAvailableError, NoRelevantChunksError
from retrieval.schemas import ChunkSearchResult

logger = logging.getLogger(__name__)

# Module-level lazy singletons — models are loaded once per process, not per request.
# Locks prevent two threads at startup from both seeing None and loading the model twice.
_embedder = None
_reranker = None
_pipeline = None
_embedder_lock = threading.Lock()
_reranker_lock = threading.Lock()
_pipeline_lock = threading.Lock()


def _get_embedder():
    global _embedder
    if _embedder is None:
        with _embedder_lock:
            if _embedder is None:
                from ingestion.embedders import SentenceTransformerEmbedder

                _embedder = SentenceTransformerEmbedder()
    return _embedder


def _get_reranker():
    global _reranker
    if _reranker is None:
        with _reranker_lock:
            if _reranker is None:
                from retrieval.reranker import CrossEncoderReranker

                _reranker = CrossEncoderReranker()
    return _reranker


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        with _pipeline_lock:
            if _pipeline is None:
                from documents.selectors import (
                    keyword_search_chunks,
                    vector_search_chunks,
                )
                from retrieval.pipeline import RetrievalPipeline

                _pipeline = RetrievalPipeline(
                    embedder=_get_embedder(),
                    vector_search_fn=vector_search_chunks,
                    keyword_search_fn=keyword_search_chunks,
                    reranker=_get_reranker(),
                )
    return _pipeline


def execute_search(
    query: str,
    document_id: uuid.UUID,
    k: int,
) -> list[ChunkSearchResult]:
    """
    Run the full retrieval pipeline for a single query against one document.

    Wires together the embedder, vector search, keyword search, RRF fusion,
    and cross-encoder reranking into a single call.

    Args:
        query: The user's search query string.
        document_id: UUID of the document to search within.
        k: Number of results to return.

    Returns:
        List of ChunkSearchResult ordered by relevance score descending.

    Raises:
        DocumentNotFoundError: if no document with document_id exists (404).
        NoRelevantChunksError: if the pipeline returns no results (404).
    """
    # Local import breaks the circular chain: query → documents → models → apps → query.
    from documents.selectors import get_document_by_id

    # Validate the document exists before running the expensive pipeline.
    get_document_by_id(document_id)  # raises DocumentNotFoundError if missing

    results = _get_pipeline().run(query=query, document_id=document_id, k=k)

    if not results:
        raise NoRelevantChunksError(
            f"No relevant chunks found for query in document {document_id}"
        )

    logger.info(
        "Search complete",
        extra={
            "document_id": str(document_id),
            "query_length": len(query),
            "result_count": len(results),
        },
    )
    return results


# ---------------------------------------------------------------------------
# LLM provider registry — lazy singletons, built once per process
# ---------------------------------------------------------------------------

_provider_registry: dict | None = None
_provider_registry_lock = threading.Lock()

_fallback_client = None
_fallback_client_lock = threading.Lock()

_semantic_cache = None
_semantic_cache_lock = threading.Lock()


def _get_semantic_cache():
    global _semantic_cache
    if _semantic_cache is None:
        with _semantic_cache_lock:
            if _semantic_cache is None:
                from query.semantic_cache import SemanticCache

                _semantic_cache = SemanticCache()
    return _semantic_cache


def _get_provider_registry() -> dict:
    """
    Build a registry of {model_name: provider_instance} at startup.

    Only includes providers whose credentials are actually configured.
    Requesting a model not in the registry raises ModelNotAvailableError (400).
    """
    global _provider_registry
    if _provider_registry is None:
        with _provider_registry_lock:
            if _provider_registry is None:
                from django.conf import settings
                from django.core.exceptions import ImproperlyConfigured

                from generation.llm import (
                    AnthropicProvider,
                    BedrockProvider,
                    FallbackLLMClient,  # noqa: F401 — imported here to warm the module
                    OllamaProvider,
                    OpenAIProvider,
                )

                registry: dict = {}

                if settings.OPENAI_API_KEY:
                    registry[settings.OPENAI_MODEL] = OpenAIProvider(
                        api_key=settings.OPENAI_API_KEY,
                        model=settings.OPENAI_MODEL,
                    )

                if settings.ANTHROPIC_API_KEY:
                    registry[settings.ANTHROPIC_MODEL] = AnthropicProvider(
                        api_key=settings.ANTHROPIC_API_KEY,
                        model=settings.ANTHROPIC_MODEL,
                    )

                if settings.BEDROCK_ENABLED and settings.BEDROCK_AWS_ACCESS_KEY_ID:
                    registry[settings.BEDROCK_MODEL_ID] = BedrockProvider(
                        aws_access_key_id=settings.BEDROCK_AWS_ACCESS_KEY_ID,
                        aws_secret_access_key=settings.BEDROCK_AWS_SECRET_ACCESS_KEY,
                        aws_region=settings.BEDROCK_AWS_REGION,
                        model_id=settings.BEDROCK_MODEL_ID,
                    )

                if settings.OLLAMA_ENABLED:
                    registry[settings.OLLAMA_MODEL] = OllamaProvider(
                        base_url=settings.OLLAMA_BASE_URL,
                        model=settings.OLLAMA_MODEL,
                    )

                if not registry:
                    raise ImproperlyConfigured(
                        "No LLM provider configured. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, "
                        "BEDROCK_ENABLED=true, or OLLAMA_ENABLED=true in your .env file."
                    )

                _provider_registry = registry
    return _provider_registry


def _get_fallback_client():
    """
    Wrap all configured providers in a FallbackLLMClient.
    Used when the caller does not specify a model — tries providers in registry order.
    """
    global _fallback_client
    if _fallback_client is None:
        with _fallback_client_lock:
            if _fallback_client is None:
                from generation.llm import FallbackLLMClient

                providers = list(_get_provider_registry().values())
                _fallback_client = FallbackLLMClient(providers=providers)
    return _fallback_client


def _resolve_provider(model: str | None):
    """
    Route a model name to its provider instance.

    model=None  → FallbackLLMClient (tries all configured providers in order)
    model="gpt-4o" → OpenAIProvider directly (no fallback)

    Raises ModelNotAvailableError (400) if the requested model is not configured.
    """
    if model is None:
        return _get_fallback_client()

    registry = _get_provider_registry()
    if model not in registry:
        available = list(registry.keys())
        raise ModelNotAvailableError(
            f"Model '{model}' is not configured. Available models: {available}"
        )
    return registry[model]


def _resolve_citations(answer_text: str, chunks: list[ChunkSearchResult]) -> list:
    """
    Extract [1], [2] markers from the answer and map them to chunk metadata.

    Runs after the stream completes — no latency impact on token delivery.
    Returns an empty list if no markers are found (graceful degradation).
    """
    from generation.schemas import Citation

    markers = re.findall(r"\[(\d+)\]", answer_text)
    seen: set[int] = set()
    citations = []

    for marker in markers:
        idx = int(marker) - 1  # [1] → index 0
        if idx in seen or idx < 0 or idx >= len(chunks):
            continue
        seen.add(idx)
        chunk = chunks[idx]
        from generation.constants import CITATION_QUOTE_MAX_CHARS

        citations.append(
            Citation(
                chunk_id=str(chunk.chunk_id),
                document_title=chunk.document_title,
                page_number=chunk.page_number,
                quote=chunk.parent_text[:CITATION_QUOTE_MAX_CHARS],
            )
        )

    return citations


# ---------------------------------------------------------------------------
# execute_ask — LLM generation composition root
# ---------------------------------------------------------------------------


def execute_ask(
    query: str,
    document_id: uuid.UUID,
    k: int,
    model: str | None = None,
) -> Iterator[str]:
    """
    Retrieve relevant chunks then stream a grounded LLM answer as SSE events.

    Yields SSE strings. Pre-stream errors (document not found, model not available,
    no chunks) are raised as exceptions — catch them in the view before the stream
    starts and return a normal HTTP error response.

    Mid-stream LLM errors are yielded as an SSE error event because the HTTP
    status code and headers are already sent once streaming begins.

    Args:
        query: The user's question.
        document_id: UUID of the document to answer from.
        k: Number of chunks to retrieve (default 5 for generation, 10 for search).
        model: Model name to use (e.g. "gpt-4o"). None = auto-fallback chain.

    Yields:
        SSE-formatted strings: token events, then citations event, then done event.

    Raises (before stream starts):
        DocumentNotFoundError: document UUID not in DB (404).
        ModelNotAvailableError: requested model not configured (400).
        NoRelevantChunksError: pipeline returned no results (404).
    """
    from django.conf import settings

    from documents.selectors import get_document_by_id
    from generation.llm import AnswerGenerationError
    from generation.prompts import build_user_message, get_system_prompt
    from generation.streaming import (
        build_sse_citations_event,
        build_sse_done_event,
        build_sse_error_event,
        build_sse_token_event,
        stream_answer_tokens,
    )

    # --- Pre-stream validation (errors here → normal HTTP response, no stream) ---
    get_document_by_id(document_id)  # raises DocumentNotFoundError (404)
    provider = _resolve_provider(model)  # raises ModelNotAvailableError (400)

    # --- Semantic cache check (before expensive retrieval + LLM call) ---
    cache = _get_semantic_cache()
    cached = cache.lookup(query, document_id)
    if cached is not None:
        from generation.schemas import Citation

        cached_answer: str = cached.get("answer", "")
        cached_citations = [Citation(**c) for c in cached.get("citations", [])]
        yield build_sse_token_event(cached_answer)
        yield build_sse_citations_event(cached_citations)
        yield build_sse_done_event()
        return

    chunks = _get_pipeline().run(query=query, document_id=document_id, k=k)
    if not chunks:
        raise NoRelevantChunksError(
            f"No relevant chunks found for query in document {document_id}"
        )

    system_prompt = get_system_prompt()
    user_message = build_user_message(
        query,
        chunks,
        max_context_tokens=settings.DOCUMIND_MAX_CONTEXT_TOKENS,
    )

    logger.info(
        "LLM generation started",
        extra={
            "document_id": str(document_id),
            "provider": type(provider).__name__,
            "model": model or "fallback",
            "chunk_count": len(chunks),
        },
    )

    # --- Stream phase (errors here → SSE error event, stream already open) ---
    accumulated = ""
    start_time = time.monotonic()
    first_token_time: float | None = None

    try:
        for i, token in enumerate(
            stream_answer_tokens(
                provider,
                system_prompt,
                user_message,
                temperature=settings.DOCUMIND_LLM_TEMPERATURE,
                max_tokens=settings.DOCUMIND_LLM_MAX_TOKENS,
                timeout=settings.DOCUMIND_LLM_TIMEOUT_SECONDS,
            )
        ):
            if i == 0:
                first_token_time = time.monotonic() - start_time
            accumulated += token
            yield build_sse_token_event(token)

        citations = _resolve_citations(accumulated, chunks)

        if not citations and re.search(r"\[\d+\]", accumulated):
            logger.warning(
                "Citation markers in answer could not be resolved to chunks",
                extra={"document_id": str(document_id), "chunk_count": len(chunks)},
            )

        yield build_sse_citations_event(citations)
        yield build_sse_done_event()

        # Store successful answer in semantic cache for future identical/similar queries.
        cache.store(
            query,
            document_id,
            {
                "answer": accumulated,
                "citations": [c.model_dump() for c in citations],
            },
        )

        total_time = time.monotonic() - start_time
        logger.info(
            "LLM generation complete",
            extra={
                "document_id": str(document_id),
                "provider": type(provider).__name__,
                "answer_length": len(accumulated),
                "citation_count": len(citations),
                "ttft_ms": round(first_token_time * 1000)
                if first_token_time is not None
                else None,
                "total_ms": round(total_time * 1000),
            },
        )

    except AnswerGenerationError as exc:
        logger.error(
            "LLM generation failed",
            extra={
                "document_id": str(document_id),
                "provider": type(provider).__name__,
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        )
        yield build_sse_error_event(str(exc))
