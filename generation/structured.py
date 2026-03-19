"""
generation/structured.py — Non-streaming, structured LLM completions via Instructor.

Streaming (generation/llm.py) is for user-facing answers — the user sees tokens
appear one at a time. Structured output (this file) is for agent-internal steps —
the LLM fills in a typed Pydantic model and returns it complete.

Instructor patches the OpenAI client to:
  1. Convert the Pydantic model into a JSON Schema tool definition
  2. Ask the LLM to fill in that schema
  3. Validate and return a real Python object

Usage:
    client = StructuredLLMClient(api_key=settings.OPENAI_API_KEY, model=settings.OPENAI_MODEL)
    result = client.complete(
        system_prompt="...",
        user_message="...",
        response_model=ComplexityClassification,
        temperature=0.0,
        max_tokens=200,
        timeout=45.0,
    )
    # result is a validated ComplexityClassification instance
"""

import logging
from typing import TypeVar

from langsmith import traceable

from generation.llm import AnswerGenerationError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class StructuredLLMClient:
    """
    Instructor-backed client for non-streaming structured LLM completions.

    Returns validated Pydantic model instances. Satisfies agents/protocols.StructuredLLMPort.

    The underlying OpenAI client is created lazily on the first call so that
    importing this module never triggers network activity or credential checks.
    """

    def __init__(self, api_key: str, model: str, *, base_url: str | None = None) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url  # None = use OpenAI default; set for Ollama/custom endpoints
        self._client = None

    def _get_client(self):
        """
        Lazily initialise the Instructor-patched OpenAI client.

        Called once per worker process — subsequent calls return the cached client.
        Same lazy-init pattern as the Redis connection pool in documents/services.py.

        When base_url is set (e.g. Ollama at http://localhost:11434/v1):
          - The OpenAI client points at that endpoint instead of api.openai.com.
          - Instructor is patched with Mode.JSON so the LLM outputs a plain JSON
            object matching the Pydantic schema. This is more reliable on small local
            models (like llama3.2) than tool-calling mode, which requires the model
            to correctly invoke a function schema — something 3B models do poorly.

        When base_url is None (OpenAI/Anthropic in staging/production):
          - Instructor uses its default mode (tool calling + function schemas), which
            OpenAI's models handle with high accuracy.
        """
        if self._client is None:
            import instructor
            import openai

            http_client = (
                openai.OpenAI(base_url=self._base_url, api_key=self._api_key)
                if self._base_url
                else openai.OpenAI(api_key=self._api_key)
            )
            # JSON mode for local/custom endpoints — tool-calling for OpenAI.
            mode = instructor.Mode.JSON if self._base_url else instructor.Mode.TOOLS
            self._client = instructor.from_openai(http_client, mode=mode)
        return self._client

    @traceable(name="structured_llm_generate_text")
    def generate_text(
        self,
        system_prompt: str,
        user_message: str,
        *,
        temperature: float,
        max_tokens: int,
        timeout: float,
    ) -> str:
        """
        Plain text generation — bypasses Instructor entirely.

        Used by generation nodes (generate_answer, synthesize) that only need
        a string back. Instructor's JSON mode prompts trigger built-in tool
        calling on some models (qwen2.5) which corrupts the response.
        Raw API calls return clean prose that these nodes simply return as-is.
        """
        import openai

        raw_client = (
            openai.OpenAI(base_url=self._base_url, api_key=self._api_key)
            if self._base_url
            else openai.OpenAI(api_key=self._api_key)
        )
        try:
            response = raw_client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            logger.error("structured_llm_generate_text_failed", extra={"model": self._model, "error": str(exc)})
            raise AnswerGenerationError(str(exc)) from exc

    @traceable(name="structured_llm_complete")
    def complete(
        self,
        system_prompt: str,
        user_message: str,
        response_model: type[T],
        *,
        temperature: float,
        max_tokens: int,
        timeout: float,
    ) -> T:
        """
        Call the LLM and return a validated instance of response_model.

        Args:
            system_prompt:  Instructions that set the LLM's role and rules.
            user_message:   The actual input to process (question, text to analyse, etc.).
            response_model: A Pydantic model class. Instructor converts this to a
                            JSON Schema tool and validates the LLM's response against it.
            temperature:    0.0 = deterministic (use for classify/plan steps).
                            >0.0 = creative (use for synthesis/generation steps).
            max_tokens:     Hard cap on LLM output length.
            timeout:        Seconds before the request is abandoned.

        Returns:
            A validated instance of response_model.

        Raises:
            AnswerGenerationError: if the LLM call fails for any reason (network,
                                   validation, rate limit, etc.).
        """
        logger.debug(
            "structured_llm_complete_start",
            extra={"model": self._model, "response_model": response_model.__name__},
        )
        try:
            result = self._get_client().chat.completions.create(
                model=self._model,
                response_model=response_model,
                max_retries=0,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
            logger.debug(
                "structured_llm_complete_success",
                extra={"model": self._model, "response_model": response_model.__name__},
            )
            return result
        except Exception as exc:
            logger.error(
                "structured_llm_complete_failed",
                extra={"model": self._model, "error": str(exc)},
            )
            raise AnswerGenerationError(str(exc)) from exc
