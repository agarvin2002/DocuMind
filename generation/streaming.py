from __future__ import annotations

import json
from collections.abc import Iterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from generation.schemas import Citation


def stream_answer_tokens(
    llm_client: object,
    system_prompt: str,
    user_message: str,
    *,
    temperature: float,
    max_tokens: int,
    timeout: float,
) -> Iterator[str]:
    """
    Delegate to llm_client.stream() and yield raw token strings.

    llm_client must satisfy LLMProviderPort — either a single provider or
    FallbackLLMClient. Both expose the same stream() interface.

    Raises AnswerGenerationError if the provider fails.
    """
    yield from llm_client.stream(
        system_prompt=system_prompt,
        user_message=user_message,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )


def build_sse_token_event(token: str) -> str:
    """
    Wrap a single token in the SSE data format.

    Wire format: data: <token>\n\n
    The double newline signals end-of-message to the client.
    """
    return f"data: {token}\n\n"


def build_sse_citations_event(citations: list[Citation]) -> str:
    """
    Send all resolved citations as a single SSE event after the token stream ends.

    Wire format:
        event: citations
        data: [{"chunk_id": "...", "document_title": "...", ...}]

    Sent once — after the last token, before the done event.
    """
    payload = json.dumps([c.model_dump() for c in citations])
    return f"event: citations\ndata: {payload}\n\n"


def build_sse_error_event(message: str) -> str:
    """
    Send an error message as an SSE event.

    Used for mid-stream LLM failures only. Pre-stream errors (document not found,
    model not available) return normal HTTP responses — not SSE events — because
    the stream has not started yet.

    Wire format:
        event: error
        data: <message>
    """
    return f"event: error\ndata: {message}\n\n"


def build_sse_done_event() -> str:
    """
    Signal that the stream is complete.

    Wire format:
        event: done
        data: [DONE]

    Clients should close the connection on receiving this event.
    """
    return "event: done\ndata: [DONE]\n\n"
