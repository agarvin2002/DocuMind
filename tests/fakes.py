"""
tests/fakes.py — Shared test doubles for the DocuMind test suite.
Importable from any test: from tests.fakes import FakeLLMProvider
"""

from __future__ import annotations

from collections.abc import Iterator

from generation.llm import AnswerGenerationError


class FakeLLMProvider:
    """
    A test double that satisfies LLMProviderPort.
    Pass tokens= for a successful stream, should_fail=True to raise on every call.
    """

    def __init__(self, tokens: list[str] | None = None, should_fail: bool = False) -> None:
        self._tokens = tokens or ["Hello", " world"]
        self._should_fail = should_fail
        self.call_count = 0

    def stream(
        self,
        system_prompt: str,
        user_message: str,
        *,
        temperature: float,
        max_tokens: int,
        timeout: float,
    ) -> Iterator[str]:
        self.call_count += 1
        if self._should_fail:
            raise AnswerGenerationError("fake provider failure")
        yield from self._tokens
