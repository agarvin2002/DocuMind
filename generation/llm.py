from __future__ import annotations

import logging
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
                    yield chunk.choices[0].delta.content
        except openai.RateLimitError as exc:
            raise AnswerGenerationError(f"OpenAI rate limit exceeded: {exc}") from exc
        except openai.BadRequestError as exc:
            raise AnswerGenerationError(f"OpenAI bad request (context too long?): {exc}") from exc
        except openai.APITimeoutError as exc:
            raise AnswerGenerationError(f"OpenAI request timed out: {exc}") from exc
        except openai.APIError as exc:
            raise AnswerGenerationError(f"OpenAI API error: {exc}") from exc


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

        try:
            with self._get_client().messages.stream(
                model=self._model,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            ) as stream:
                yield from stream.text_stream
        except anthropic.RateLimitError as exc:
            raise AnswerGenerationError(f"Anthropic rate limit exceeded: {exc}") from exc
        except anthropic.BadRequestError as exc:
            raise AnswerGenerationError(f"Anthropic bad request: {exc}") from exc
        except anthropic.APITimeoutError as exc:
            raise AnswerGenerationError(f"Anthropic request timed out: {exc}") from exc
        except anthropic.APIError as exc:
            raise AnswerGenerationError(f"Anthropic API error: {exc}") from exc


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

        try:
            with self._get_client().messages.stream(
                model=self._model_id,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            ) as stream:
                yield from stream.text_stream
        except anthropic.APIError as exc:
            raise AnswerGenerationError(f"Bedrock API error: {exc}") from exc
        except Exception as exc:
            raise self._wrap_bedrock_error(exc) from exc


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

            self._client = openai.OpenAI(base_url=self._base_url, api_key=OLLAMA_DUMMY_API_KEY)
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
                    yield chunk.choices[0].delta.content
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


# ---------------------------------------------------------------------------
# Fallback client — Chain of Responsibility
# ---------------------------------------------------------------------------


class FallbackLLMClient:
    """
    Tries providers in order until one succeeds.

    Design pattern: Chain of Responsibility.
    Adding a new provider requires zero changes to this class —
    just append it to the providers list in the composition root.
    """

    def __init__(self, providers: list[LLMProviderPort]) -> None:
        if not providers:
            raise ValueError("FallbackLLMClient requires at least one provider.")
        self._providers = providers

    def stream(
        self,
        system_prompt: str,
        user_message: str,
        *,
        temperature: float,
        max_tokens: int,
        timeout: float,
    ) -> Iterator[str]:
        last_exc: AnswerGenerationError | None = None
        for i, provider in enumerate(self._providers):
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
                if i < len(self._providers) - 1:
                    logger.debug(
                        "LLM provider failed, trying next",
                        extra={
                            "failed_provider": type(provider).__name__,
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        },
                    )
        logger.error(
            "All LLM providers failed",
            extra={"providers_tried": [type(p).__name__ for p in self._providers]},
        )
        if last_exc is None:
            raise AnswerGenerationError("No providers were available to handle the request.")
        raise last_exc
