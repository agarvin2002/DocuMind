from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from langsmith import traceable

from core.exceptions import LLMError
from generation.constants import OLLAMA_DUMMY_API_KEY

if TYPE_CHECKING:
    import anthropic
    import openai

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Port (interface) — anything that satisfies this can be used as a provider
# ---------------------------------------------------------------------------


@runtime_checkable
class LLMProviderPort(Protocol):
    """
    Structural interface for LLM providers.

    Any class with stream() matching this signature automatically satisfies
    this protocol — no inheritance needed.
    """

    def stream(
        self,
        system_prompt: str,
        user_message: str,
        *,
        temperature: float,
        max_tokens: int,
        timeout: float,
    ) -> Iterator[str]: ...


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class AnswerGenerationError(LLMError):
    """Raised when all LLM providers fail or a single provider errors out."""

    default_message = "Failed to generate an answer from any configured LLM provider."


# ---------------------------------------------------------------------------
# OpenAI provider
# ---------------------------------------------------------------------------


class OpenAIProvider:
    """
    Wraps openai.OpenAI.
    stream() yields raw tokens for the /ask/ SSE endpoint.
    """

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._client: openai.OpenAI | None = None

    def _get_client(self) -> openai.OpenAI:
        if self._client is None:
            import openai

            self._client = openai.OpenAI(api_key=self._api_key)
        return self._client

    @traceable(name="openai_stream", run_type="llm")
    def stream(
        self,
        system_prompt: str,
        user_message: str,
        *,
        temperature: float,
        max_tokens: int,
        timeout: float,
    ) -> Iterator[str]:
        import openai

        start = time.monotonic()
        first_token_time: float | None = None
        tokens_yielded = 0
        success = False
        try:
            response = self._get_client().chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                stream=True,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    if first_token_time is None:
                        first_token_time = time.monotonic()
                    tokens_yielded += 1
                    yield chunk.choices[0].delta.content
            success = True
        except openai.RateLimitError as exc:
            raise AnswerGenerationError(f"OpenAI rate limit exceeded: {exc}") from exc
        except openai.BadRequestError as exc:
            raise AnswerGenerationError(
                f"OpenAI bad request (context too long?): {exc}"
            ) from exc
        except openai.APITimeoutError as exc:
            raise AnswerGenerationError(f"OpenAI request timed out: {exc}") from exc
        except openai.APIError as exc:
            raise AnswerGenerationError(f"OpenAI API error: {exc}") from exc
        finally:
            total_ms = (time.monotonic() - start) * 1000
            ttft_ms = (first_token_time - start) * 1000 if first_token_time else None
            logger.info(
                "llm_stream_complete",
                extra={
                    "provider": "OpenAI",
                    "model": self._model,
                    "ttft_ms": round(ttft_ms, 1) if ttft_ms is not None else None,
                    "tokens_yielded": tokens_yielded,
                    "total_ms": round(total_ms, 1),
                    "success": success,
                },
            )


# ---------------------------------------------------------------------------
# Anthropic provider
# ---------------------------------------------------------------------------


class AnthropicProvider:
    """
    Wraps anthropic.Anthropic (direct API — uses Anthropic billing and API key).
    stream() uses the native Anthropic streaming context manager.
    """

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._client: anthropic.Anthropic | None = None

    def _get_client(self) -> anthropic.Anthropic:
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    @traceable(name="anthropic_stream", run_type="llm")
    def stream(
        self,
        system_prompt: str,
        user_message: str,
        *,
        temperature: float,
        max_tokens: int,
        timeout: float,
    ) -> Iterator[str]:
        import anthropic

        start = time.monotonic()
        first_token_time: float | None = None
        tokens_yielded = 0
        success = False
        try:
            with self._get_client().messages.stream(
                model=self._model,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            ) as stream:
                for token in stream.text_stream:
                    if first_token_time is None:
                        first_token_time = time.monotonic()
                    tokens_yielded += 1
                    yield token
            success = True
        except anthropic.RateLimitError as exc:
            raise AnswerGenerationError(
                f"Anthropic rate limit exceeded: {exc}"
            ) from exc
        except anthropic.BadRequestError as exc:
            raise AnswerGenerationError(f"Anthropic bad request: {exc}") from exc
        except anthropic.APITimeoutError as exc:
            raise AnswerGenerationError(f"Anthropic request timed out: {exc}") from exc
        except anthropic.APIError as exc:
            raise AnswerGenerationError(f"Anthropic API error: {exc}") from exc
        finally:
            total_ms = (time.monotonic() - start) * 1000
            ttft_ms = (first_token_time - start) * 1000 if first_token_time else None
            logger.info(
                "llm_stream_complete",
                extra={
                    "provider": "Anthropic",
                    "model": self._model,
                    "ttft_ms": round(ttft_ms, 1) if ttft_ms is not None else None,
                    "tokens_yielded": tokens_yielded,
                    "total_ms": round(total_ms, 1),
                    "success": success,
                },
            )


# ---------------------------------------------------------------------------
# Bedrock provider
# ---------------------------------------------------------------------------


class BedrockProvider:
    """
    Runs Claude models on AWS Bedrock via Anthropic's SDK.

    Uses anthropic.AnthropicBedrock — same SDK interface as AnthropicProvider,
    authenticated with AWS credentials instead of an Anthropic API key.
    Data stays inside the AWS VPC — required for GDPR/HIPAA compliance.

    Model IDs use AWS Bedrock format: "anthropic.claude-3-sonnet-20240229-v1:0"
    The model must be enabled in AWS Console → Bedrock → Model access before use.
    """

    def __init__(
        self,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        aws_region: str,
        model_id: str,
    ) -> None:
        self._aws_access_key_id = aws_access_key_id
        self._aws_secret_access_key = aws_secret_access_key
        self._aws_region = aws_region
        self._model_id = model_id
        self._client: anthropic.AnthropicBedrock | None = None

    def _get_client(self) -> anthropic.AnthropicBedrock:
        if self._client is None:
            from anthropic import AnthropicBedrock

            self._client = AnthropicBedrock(
                aws_access_key=self._aws_access_key_id,
                aws_secret_key=self._aws_secret_access_key,
                aws_region=self._aws_region,
            )
        return self._client

    def _wrap_bedrock_error(self, exc: Exception) -> AnswerGenerationError:
        """Map botocore/Bedrock errors to AnswerGenerationError with helpful messages."""
        exc_str = str(exc)
        exc_type = type(exc).__name__

        if "NoCredentialsError" in exc_type or "NoCredentialsError" in exc_str:
            return AnswerGenerationError(
                "AWS credentials not found. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY."
            )
        if "AccessDeniedException" in exc_str or "AccessDenied" in exc_str:
            return AnswerGenerationError(
                f"AWS access denied for Bedrock model '{self._model_id}'. "
                "Check IAM permissions: bedrock:InvokeModel and bedrock:InvokeModelWithResponseStream."
            )
        if "ValidationException" in exc_str and "model" in exc_str.lower():
            return AnswerGenerationError(
                f"Bedrock model '{self._model_id}' is not enabled. "
                "Enable it in AWS Console → Bedrock → Model access."
            )
        return AnswerGenerationError(f"Bedrock error ({exc_type}): {exc}")

    @traceable(name="bedrock_stream", run_type="llm")
    def stream(
        self,
        system_prompt: str,
        user_message: str,
        *,
        temperature: float,
        max_tokens: int,
        timeout: float,
    ) -> Iterator[str]:
        import anthropic

        start = time.monotonic()
        first_token_time: float | None = None
        tokens_yielded = 0
        success = False
        try:
            with self._get_client().messages.stream(
                model=self._model_id,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            ) as stream:
                for token in stream.text_stream:
                    if first_token_time is None:
                        first_token_time = time.monotonic()
                    tokens_yielded += 1
                    yield token
            success = True
        except anthropic.APIError as exc:
            raise AnswerGenerationError(f"Bedrock API error: {exc}") from exc
        except Exception as exc:
            raise self._wrap_bedrock_error(exc) from exc
        finally:
            total_ms = (time.monotonic() - start) * 1000
            ttft_ms = (first_token_time - start) * 1000 if first_token_time else None
            logger.info(
                "llm_stream_complete",
                extra={
                    "provider": "Bedrock",
                    "model": self._model_id,
                    "ttft_ms": round(ttft_ms, 1) if ttft_ms is not None else None,
                    "tokens_yielded": tokens_yielded,
                    "total_ms": round(total_ms, 1),
                    "success": success,
                },
            )


# ---------------------------------------------------------------------------
# Ollama provider
# ---------------------------------------------------------------------------


class OllamaProvider:
    """
    Wraps a local Ollama instance via its OpenAI-compatible API.

    Ollama exposes the same REST interface as OpenAI at localhost:11434/v1,
    so we reuse the openai SDK with a different base_url.
    No real API key needed — Ollama ignores it but the SDK requires a non-empty string.

    The model must be pulled before first use:
        docker compose exec ollama ollama pull llama3.2
    """

    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url
        self._model = model
        self._client: openai.OpenAI | None = None

    def _get_client(self) -> openai.OpenAI:
        if self._client is None:
            import openai

            self._client = openai.OpenAI(
                base_url=self._base_url, api_key=OLLAMA_DUMMY_API_KEY
            )
        return self._client

    @traceable(name="ollama_stream", run_type="llm")
    def stream(
        self,
        system_prompt: str,
        user_message: str,
        *,
        temperature: float,
        max_tokens: int,
        timeout: float,
    ) -> Iterator[str]:
        import openai

        start = time.monotonic()
        first_token_time: float | None = None
        tokens_yielded = 0
        success = False
        try:
            response = self._get_client().chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                stream=True,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    if first_token_time is None:
                        first_token_time = time.monotonic()
                    tokens_yielded += 1
                    yield chunk.choices[0].delta.content
            success = True
        except ConnectionError as exc:
            raise AnswerGenerationError(
                f"Local Ollama is not running at {self._base_url}. "
                "Start it with: docker compose up -d ollama"
            ) from exc
        except openai.NotFoundError as exc:
            raise AnswerGenerationError(
                f"Ollama model '{self._model}' not found. "
                f"Pull it with: docker compose exec ollama ollama pull {self._model}"
            ) from exc
        except openai.APIError as exc:
            raise AnswerGenerationError(f"Ollama error: {exc}") from exc
        finally:
            total_ms = (time.monotonic() - start) * 1000
            ttft_ms = (first_token_time - start) * 1000 if first_token_time else None
            logger.info(
                "llm_stream_complete",
                extra={
                    "provider": "Ollama",
                    "model": self._model,
                    "ttft_ms": round(ttft_ms, 1) if ttft_ms is not None else None,
                    "tokens_yielded": tokens_yielded,
                    "total_ms": round(total_ms, 1),
                    "success": success,
                },
            )


# ---------------------------------------------------------------------------
# Fallback client — Chain of Responsibility
# ---------------------------------------------------------------------------


class FallbackLLMClient:
    """
    Tries providers in order until one succeeds.

    Design pattern: Chain of Responsibility.
    Adding a new provider requires zero changes to this class —
    just append it to the providers list in the composition root.

    Circuit breaker: a provider that raises AnswerGenerationError is placed
    in a cooldown window (default 60 s). During cooldown, the provider is
    skipped without attempting a call so its timeout does not add latency.
    All providers are tried as a last resort if every circuit is open.
    """

    _CIRCUIT_BREAKER_COOLDOWN: float = 60.0  # seconds

    def __init__(self, providers: list[LLMProviderPort]) -> None:
        if not providers:
            raise ValueError("FallbackLLMClient requires at least one provider.")
        self._providers = providers
        # Maps provider class name → monotonic time of last failure.
        self._failure_times: dict[str, float] = {}

    def _is_open(self, provider: LLMProviderPort) -> bool:
        """Return True if this provider is in cooldown (circuit open, should skip)."""
        last_fail = self._failure_times.get(type(provider).__name__)
        if last_fail is None:
            return False
        return (time.monotonic() - last_fail) < self._CIRCUIT_BREAKER_COOLDOWN

    def _trip(self, provider: LLMProviderPort) -> None:
        """Record a failure and open the circuit for this provider."""
        self._failure_times[type(provider).__name__] = time.monotonic()

    def stream(
        self,
        system_prompt: str,
        user_message: str,
        *,
        temperature: float,
        max_tokens: int,
        timeout: float,
    ) -> Iterator[str]:
        # Prefer providers whose circuits are closed; fall back to open ones.
        closed = [p for p in self._providers if not self._is_open(p)]
        open_ = [p for p in self._providers if self._is_open(p)]
        ordered = closed + open_

        last_exc: AnswerGenerationError | None = None
        for provider in ordered:
            if self._is_open(provider):
                logger.warning(
                    "LLM provider circuit open, trying anyway (last resort)",
                    extra={"provider": type(provider).__name__},
                )
            try:
                yield from provider.stream(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                )
                logger.info(
                    "LLM provider stream succeeded",
                    extra={"provider": type(provider).__name__},
                )
                return
            except AnswerGenerationError as exc:
                last_exc = exc
                self._trip(provider)
                logger.warning(
                    "LLM provider failed, circuit tripped",
                    extra={
                        "failed_provider": type(provider).__name__,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "cooldown_seconds": self._CIRCUIT_BREAKER_COOLDOWN,
                    },
                )
        logger.error(
            "All LLM providers failed",
            extra={"providers_tried": [type(p).__name__ for p in ordered]},
        )
        if last_exc is None:
            raise AnswerGenerationError(
                "No providers were available to handle the request."
            )
        raise last_exc
