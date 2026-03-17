"""
Unit tests for generation/structured.py.

The Instructor/OpenAI client is mocked so tests run without network access
or valid API credentials.
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from generation.llm import AnswerGenerationError
from generation.structured import StructuredLLMClient

# ---------------------------------------------------------------------------
# Minimal Pydantic model for use in tests
# ---------------------------------------------------------------------------


class _FakeOutput(BaseModel):
    answer: str
    score: int


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStructuredLLMClient:
    def _make_client(self) -> StructuredLLMClient:
        return StructuredLLMClient(api_key="test-key", model="gpt-4o")

    def _mock_instructor(self, return_value):
        """Return a context manager that patches the instructor client."""
        mock_instructor_client = MagicMock()
        mock_instructor_client.chat.completions.create.return_value = return_value
        return patch.object(
            StructuredLLMClient,
            "_get_client",
            return_value=mock_instructor_client,
        ), mock_instructor_client

    def test_complete_returns_validated_pydantic_model(self):
        expected = _FakeOutput(answer="hello", score=42)
        ctx, mock_client = self._mock_instructor(expected)

        with ctx:
            client = self._make_client()
            result = client.complete(
                system_prompt="You are a test.",
                user_message="What is the answer?",
                response_model=_FakeOutput,
                temperature=0.0,
                max_tokens=100,
                timeout=10.0,
            )

        assert result is expected
        assert result.answer == "hello"
        assert result.score == 42

    def test_system_and_user_messages_are_passed_correctly(self):
        expected = _FakeOutput(answer="ok", score=1)
        ctx, mock_client = self._mock_instructor(expected)

        with ctx:
            client = self._make_client()
            client.complete(
                system_prompt="Be precise.",
                user_message="Classify this question.",
                response_model=_FakeOutput,
                temperature=0.0,
                max_tokens=50,
                timeout=5.0,
            )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        messages = call_kwargs["messages"]
        assert messages[0] == {"role": "system", "content": "Be precise."}
        assert messages[1] == {"role": "user", "content": "Classify this question."}

    def test_response_model_is_forwarded_to_instructor(self):
        expected = _FakeOutput(answer="ok", score=1)
        ctx, mock_client = self._mock_instructor(expected)

        with ctx:
            client = self._make_client()
            client.complete(
                system_prompt="sys",
                user_message="usr",
                response_model=_FakeOutput,
                temperature=0.0,
                max_tokens=50,
                timeout=5.0,
            )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["response_model"] is _FakeOutput

    def test_complete_raises_answer_generation_error_on_api_error(self):
        with patch.object(
            StructuredLLMClient,
            "_get_client",
            side_effect=RuntimeError("network failure"),
        ):
            client = self._make_client()
            with pytest.raises(AnswerGenerationError):
                client.complete(
                    system_prompt="sys",
                    user_message="usr",
                    response_model=_FakeOutput,
                    temperature=0.0,
                    max_tokens=50,
                    timeout=5.0,
                )

    def test_client_is_lazily_initialized(self):
        client = self._make_client()
        assert client._client is None  # not yet initialised

        # instructor is a local import inside _get_client — patch it in its own namespace
        with (
            patch("instructor.from_openai", return_value=MagicMock()) as mock_from_openai,
            patch("openai.OpenAI"),
        ):
            client._get_client()

        assert client._client is not None
        mock_from_openai.assert_called_once()

    def test_second_get_client_call_reuses_instance(self):
        client = self._make_client()
        mock_inner = MagicMock()

        with (
            patch("instructor.from_openai", return_value=mock_inner) as mock_from_openai,
            patch("openai.OpenAI"),
        ):
            first = client._get_client()
            second = client._get_client()

        assert first is second
        # instructor.from_openai should only be called once
        mock_from_openai.assert_called_once()
