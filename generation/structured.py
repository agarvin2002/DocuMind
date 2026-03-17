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

    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._client = None

    def _get_client(self):
        """
        Lazily initialise the Instructor-patched OpenAI client.

        Called once per worker process — subsequent calls return the cached client.
        Same lazy-init pattern as the Redis connection pool in documents/services.py.
        """
        if self._client is None:
            import instructor
            import openai

            self._client = instructor.from_openai(
                openai.OpenAI(api_key=self._api_key)
            )
        return self._client

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
