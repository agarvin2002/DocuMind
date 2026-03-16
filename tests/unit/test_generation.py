"""
Unit tests for the generation layer.
No database, no Docker, no real API keys — all external calls are faked or mocked.
"""

import json
import uuid
from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest

from generation.llm import AnswerGenerationError, FallbackLLMClient
from generation.prompts import (
    build_context_block,
    build_user_message,
    estimate_token_count,
    get_system_prompt,
)
from generation.schemas import Citation, GeneratedAnswer
from generation.streaming import (
    build_sse_citations_event,
    build_sse_done_event,
    build_sse_error_event,
    build_sse_token_event,
)
from retrieval.schemas import ChunkSearchResult

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_chunk(
    chunk_id: str = "chunk-1",
    page_number: int = 1,
    child_text: str = "short child",
    parent_text: str = "longer parent text used by the LLM",
    score: float = 0.9,
) -> ChunkSearchResult:
    return ChunkSearchResult(
        chunk_id=chunk_id,
        document_id="doc-1",
        document_title="Test Document",
        chunk_index=0,
        child_text=child_text,
        parent_text=parent_text,
        page_number=page_number,
        score=score,
    )


def _make_answer(answer: str = "The answer is 42.") -> GeneratedAnswer:
    return GeneratedAnswer(
        answer=answer,
        citations=[],
        model_used="fake-model",
        prompt_version="v1",
        input_token_count=10,
        output_token_count=5,
    )


class FakeLLMProvider:
    """
    A test double that satisfies LLMProviderPort.
    Pass tokens= for a successful stream, should_fail=True to raise on every call.
    """

    def __init__(self, tokens: list[str] | None = None, should_fail: bool = False) -> None:
        self._tokens = tokens or ["Hello", " world"]
        self._should_fail = should_fail
        self.call_count = 0

    def complete(
        self,
        system_prompt: str,
        user_message: str,
        *,
        temperature: float,
        max_tokens: int,
        timeout: float,
    ) -> GeneratedAnswer:
        self.call_count += 1
        if self._should_fail:
            raise AnswerGenerationError("fake provider failure")
        return _make_answer()

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


# ---------------------------------------------------------------------------
# TestGenerationSchemas
# ---------------------------------------------------------------------------


class TestGenerationSchemas:
    def test_citation_requires_all_fields(self):
        with pytest.raises(Exception):
            Citation(chunk_id="c1", document_title="Doc")  # missing page_number, quote

    def test_generated_answer_requires_all_fields(self):
        with pytest.raises(Exception):
            GeneratedAnswer(answer="ok")  # missing citations, model_used, etc.

    def test_generated_answer_serializes_to_json(self):
        citation = Citation(
            chunk_id="c1",
            document_title="My Doc",
            page_number=3,
            quote="relevant sentence",
        )
        answer = GeneratedAnswer(
            answer="The answer is [1].",
            citations=[citation],
            model_used="gpt-4o",
            prompt_version="v1",
            input_token_count=100,
            output_token_count=50,
        )
        data = answer.model_dump()
        assert data["answer"] == "The answer is [1]."
        assert data["citations"][0]["chunk_id"] == "c1"
        assert data["model_used"] == "gpt-4o"


# ---------------------------------------------------------------------------
# TestPromptBuilder
# ---------------------------------------------------------------------------


class TestPromptBuilder:
    def test_build_context_block_numbers_chunks(self):
        chunks = [_make_chunk("c1", page_number=1), _make_chunk("c2", page_number=2)]
        block = build_context_block(chunks)
        assert "[1]" in block
        assert "[2]" in block

    def test_build_context_block_uses_parent_text(self):
        chunk = _make_chunk(parent_text="THIS IS PARENT", child_text="child")
        block = build_context_block([chunk])
        assert "THIS IS PARENT" in block
        assert "child" not in block

    def test_build_context_block_includes_page_number(self):
        chunk = _make_chunk(page_number=7)
        block = build_context_block([chunk])
        assert "Page 7" in block

    def test_build_user_message_includes_query(self):
        chunk = _make_chunk()
        msg = build_user_message("What is the risk?", [chunk], max_context_tokens=8000)
        assert "What is the risk?" in msg

    def test_build_user_message_truncates_at_token_limit(self):
        # Each chunk's parent_text is 8 chars = 2 tokens (chars / 4).
        # max_context_tokens=2 fits exactly the first chunk (2 tokens),
        # but not the second (2 + 2 = 4 > 2) → only [1] should appear.
        chunk1 = _make_chunk("c1", parent_text="a" * 8)   # 2 tokens
        chunk2 = _make_chunk("c2", parent_text="b" * 8)   # 2 tokens
        msg = build_user_message("query", [chunk1, chunk2], max_context_tokens=2)
        assert "[1]" in msg
        assert "[2]" not in msg

    def test_estimate_token_count_returns_int(self):
        count = estimate_token_count("hello world")
        assert isinstance(count, int)
        assert count > 0

    def test_get_system_prompt_v1_contains_cite_instruction(self):
        prompt = get_system_prompt("v1")
        assert "[1]" in prompt or "Cite" in prompt or "cite" in prompt

    def test_get_system_prompt_raises_for_unknown_version(self):
        with pytest.raises(ValueError, match="Unknown prompt version"):
            get_system_prompt("v99")


# ---------------------------------------------------------------------------
# TestSSEFormatting
# ---------------------------------------------------------------------------


class TestSSEFormatting:
    def test_token_event_format(self):
        event = build_sse_token_event("hello")
        assert event == "data: hello\n\n"

    def test_citations_event_format(self):
        citation = Citation(
            chunk_id="c1",
            document_title="Doc",
            page_number=1,
            quote="a sentence",
        )
        event = build_sse_citations_event([citation])
        assert event.startswith("event: citations\n")
        assert "data: " in event
        payload = json.loads(event.split("data: ", 1)[1].strip())
        assert payload[0]["chunk_id"] == "c1"

    def test_done_event_format(self):
        event = build_sse_done_event()
        assert event == "event: done\ndata: [DONE]\n\n"

    def test_error_event_format(self):
        event = build_sse_error_event("something went wrong")
        assert event.startswith("event: error\n")
        assert "something went wrong" in event


# ---------------------------------------------------------------------------
# TestFallbackLLMClient
# ---------------------------------------------------------------------------


class TestFallbackLLMClient:
    def test_uses_first_provider_on_success(self):
        p1 = FakeLLMProvider(should_fail=False)
        p2 = FakeLLMProvider(should_fail=False)
        client = FallbackLLMClient(providers=[p1, p2])
        client.complete("sys", "usr", temperature=0.1, max_tokens=100, timeout=10.0)
        assert p1.call_count == 1
        assert p2.call_count == 0

    def test_stream_uses_first_provider_on_success(self):
        p1 = FakeLLMProvider(tokens=["a", "b"])
        p2 = FakeLLMProvider(tokens=["c"])
        client = FallbackLLMClient(providers=[p1, p2])
        tokens = list(client.stream("sys", "usr", temperature=0.1, max_tokens=100, timeout=10.0))
        assert tokens == ["a", "b"]
        assert p2.call_count == 0

    def test_falls_back_to_second_on_first_failure(self):
        p1 = FakeLLMProvider(should_fail=True)
        p2 = FakeLLMProvider(should_fail=False)
        client = FallbackLLMClient(providers=[p1, p2])
        result = client.complete("sys", "usr", temperature=0.1, max_tokens=100, timeout=10.0)
        assert p1.call_count == 1
        assert p2.call_count == 1
        assert isinstance(result, GeneratedAnswer)

    def test_falls_back_to_third_on_first_two_failures(self):
        p1 = FakeLLMProvider(should_fail=True)
        p2 = FakeLLMProvider(should_fail=True)
        p3 = FakeLLMProvider(should_fail=False)  # Ollama as 3rd
        client = FallbackLLMClient(providers=[p1, p2, p3])
        result = client.complete("sys", "usr", temperature=0.1, max_tokens=100, timeout=10.0)
        assert p3.call_count == 1
        assert isinstance(result, GeneratedAnswer)

    def test_stream_falls_back_through_chain(self):
        p1 = FakeLLMProvider(should_fail=True)
        p2 = FakeLLMProvider(tokens=["fallback", " token"])
        client = FallbackLLMClient(providers=[p1, p2])
        tokens = list(client.stream("sys", "usr", temperature=0.1, max_tokens=100, timeout=10.0))
        assert tokens == ["fallback", " token"]

    def test_raises_if_all_providers_fail(self):
        p1 = FakeLLMProvider(should_fail=True)
        p2 = FakeLLMProvider(should_fail=True)
        client = FallbackLLMClient(providers=[p1, p2])
        with pytest.raises(AnswerGenerationError):
            client.complete("sys", "usr", temperature=0.1, max_tokens=100, timeout=10.0)

    def test_raises_value_error_with_empty_providers(self):
        with pytest.raises(ValueError, match="at least one provider"):
            FallbackLLMClient(providers=[])


# ---------------------------------------------------------------------------
# TestBedrockProvider
# ---------------------------------------------------------------------------


class TestBedrockProvider:
    def test_no_credentials_error_raises_answer_generation_error(self):
        from generation.llm import BedrockProvider

        provider = BedrockProvider(
            aws_access_key_id="bad",
            aws_secret_access_key="bad",
            aws_region="us-east-1",
            model_id="anthropic.claude-3-sonnet-20240229-v1:0",
        )
        # Simulate NoCredentialsError coming from botocore
        with patch.object(provider, "_get_client") as mock_client:
            mock_client.return_value.messages.stream.side_effect = Exception("NoCredentialsError")
            with pytest.raises(AnswerGenerationError):
                list(
                    provider.stream(
                        "sys", "usr", temperature=0.1, max_tokens=100, timeout=10.0
                    )
                )

    def test_access_denied_raises_answer_generation_error_with_helpful_message(self):
        from generation.llm import BedrockProvider

        provider = BedrockProvider(
            aws_access_key_id="key",
            aws_secret_access_key="secret",
            aws_region="us-east-1",
            model_id="anthropic.claude-3-sonnet-20240229-v1:0",
        )
        with patch.object(provider, "_get_client") as mock_client:
            mock_client.return_value.messages.stream.side_effect = Exception(
                "AccessDeniedException"
            )
            with pytest.raises(AnswerGenerationError, match="IAM permissions"):
                list(
                    provider.stream(
                        "sys", "usr", temperature=0.1, max_tokens=100, timeout=10.0
                    )
                )

    def test_model_not_enabled_raises_answer_generation_error_with_helpful_message(self):
        from generation.llm import BedrockProvider

        provider = BedrockProvider(
            aws_access_key_id="key",
            aws_secret_access_key="secret",
            aws_region="us-east-1",
            model_id="anthropic.claude-3-sonnet-20240229-v1:0",
        )
        with patch.object(provider, "_get_client") as mock_client:
            mock_client.return_value.messages.stream.side_effect = Exception(
                "ValidationException: The model is not enabled"
            )
            with pytest.raises(AnswerGenerationError, match="not enabled"):
                list(
                    provider.stream(
                        "sys", "usr", temperature=0.1, max_tokens=100, timeout=10.0
                    )
                )


# ---------------------------------------------------------------------------
# TestOllamaProvider
# ---------------------------------------------------------------------------


class TestOllamaProvider:
    def test_connection_error_raises_answer_generation_error_with_helpful_message(self):
        from generation.llm import OllamaProvider

        provider = OllamaProvider(base_url="http://localhost:11434/v1", model="llama3.2")
        with patch.object(provider, "_get_client") as mock_client:
            mock_client.return_value.chat.completions.create.side_effect = ConnectionError(
                "Connection refused"
            )
            with pytest.raises(AnswerGenerationError, match="not running"):
                list(
                    provider.stream(
                        "sys", "usr", temperature=0.1, max_tokens=100, timeout=10.0
                    )
                )

    def test_missing_model_raises_answer_generation_error_with_helpful_message(self):
        import openai

        from generation.llm import OllamaProvider

        provider = OllamaProvider(base_url="http://localhost:11434/v1", model="llama3.2")
        with patch.object(provider, "_get_client") as mock_client:
            mock_client.return_value.chat.completions.create.side_effect = openai.NotFoundError(
                message="model not found",
                response=MagicMock(status_code=404),
                body={},
            )
            with pytest.raises(AnswerGenerationError, match="Pull it with"):
                list(
                    provider.stream(
                        "sys", "usr", temperature=0.1, max_tokens=100, timeout=10.0
                    )
                )


# ---------------------------------------------------------------------------
# TestExecuteAsk
# ---------------------------------------------------------------------------


class TestExecuteAsk:
    """
    Tests for execute_ask() in query/services.py.
    All external calls (pipeline, LLM, DB) are mocked.
    """

    def _run(self, **kwargs) -> list[str]:
        """Collect all SSE events from execute_ask() into a list."""
        from query.services import execute_ask

        return list(execute_ask(**kwargs))

    def _default_kwargs(self, model=None):
        return {
            "query": "What is the main topic?",
            "document_id": uuid.uuid4(),
            "k": 5,
            "model": model,
        }

    def test_yields_sse_token_events(self):
        with (
            patch("documents.selectors.get_document_by_id"),
            patch("query.services._get_pipeline") as mock_pipeline,
            patch("query.services._resolve_provider") as mock_resolve,
        ):
            mock_pipeline.return_value.run.return_value = [_make_chunk()]
            mock_resolve.return_value = FakeLLMProvider(tokens=["Hello", " world"])

            events = self._run(**self._default_kwargs())

        token_events = [e for e in events if e.startswith("data: ")]
        assert "data: Hello\n\n" in token_events
        assert "data:  world\n\n" in token_events

    def test_yields_citations_event_after_tokens(self):
        with (
            patch("documents.selectors.get_document_by_id"),
            patch("query.services._get_pipeline") as mock_pipeline,
            patch("query.services._resolve_provider") as mock_resolve,
        ):
            mock_pipeline.return_value.run.return_value = [_make_chunk()]
            mock_resolve.return_value = FakeLLMProvider(tokens=["Answer [1]."])

            events = self._run(**self._default_kwargs())

        citation_events = [e for e in events if "event: citations" in e]
        assert len(citation_events) == 1

    def test_yields_done_event_last(self):
        with (
            patch("documents.selectors.get_document_by_id"),
            patch("query.services._get_pipeline") as mock_pipeline,
            patch("query.services._resolve_provider") as mock_resolve,
        ):
            mock_pipeline.return_value.run.return_value = [_make_chunk()]
            mock_resolve.return_value = FakeLLMProvider(tokens=["done"])

            events = self._run(**self._default_kwargs())

        assert events[-1] == "event: done\ndata: [DONE]\n\n"

    def test_raises_document_not_found_before_stream(self):
        from documents.exceptions import DocumentNotFoundError

        with patch(
            "documents.selectors.get_document_by_id",
            side_effect=DocumentNotFoundError("not found"),
        ):
            with pytest.raises(DocumentNotFoundError):
                self._run(**self._default_kwargs())

    def test_raises_no_relevant_chunks_error_on_empty_results(self):
        from query.exceptions import NoRelevantChunksError

        with (
            patch("documents.selectors.get_document_by_id"),
            patch("query.services._get_pipeline") as mock_pipeline,
            patch("query.services._resolve_provider") as mock_resolve,
        ):
            mock_pipeline.return_value.run.return_value = []
            mock_resolve.return_value = FakeLLMProvider()

            with pytest.raises(NoRelevantChunksError):
                self._run(**self._default_kwargs())

    def test_yields_error_event_on_llm_failure(self):
        with (
            patch("documents.selectors.get_document_by_id"),
            patch("query.services._get_pipeline") as mock_pipeline,
            patch("query.services._resolve_provider") as mock_resolve,
        ):
            mock_pipeline.return_value.run.return_value = [_make_chunk()]
            mock_resolve.return_value = FakeLLMProvider(should_fail=True)

            events = self._run(**self._default_kwargs())

        error_events = [e for e in events if "event: error" in e]
        assert len(error_events) == 1
        assert "fake provider failure" in error_events[0]

    def test_citation_markers_resolved_to_chunks(self):
        chunk = _make_chunk("c-1", page_number=5, parent_text="The risk is significant.")
        with (
            patch("documents.selectors.get_document_by_id"),
            patch("query.services._get_pipeline") as mock_pipeline,
            patch("query.services._resolve_provider") as mock_resolve,
        ):
            mock_pipeline.return_value.run.return_value = [chunk]
            # Answer includes [1] marker so citation should be resolved
            mock_resolve.return_value = FakeLLMProvider(tokens=["The answer [1]."])

            events = self._run(**self._default_kwargs())

        citation_event = next(e for e in events if "event: citations" in e)
        payload = json.loads(citation_event.split("data: ", 1)[1].strip())
        assert len(payload) == 1
        assert payload[0]["chunk_id"] == "c-1"
        assert payload[0]["page_number"] == 5

    def test_raises_model_not_available_for_unconfigured_model(self):
        from query.exceptions import ModelNotAvailableError

        with (
            patch("documents.selectors.get_document_by_id"),
            patch(
                "query.services._resolve_provider",
                side_effect=ModelNotAvailableError("Model 'gpt-99' is not configured."),
            ),
        ):
            with pytest.raises(ModelNotAvailableError):
                self._run(**self._default_kwargs(model="gpt-99"))

    def test_routes_to_correct_provider_when_model_specified(self):
        specific_provider = FakeLLMProvider(tokens=["direct"])
        with (
            patch("documents.selectors.get_document_by_id"),
            patch("query.services._get_pipeline") as mock_pipeline,
            patch("query.services._resolve_provider", return_value=specific_provider),
        ):
            mock_pipeline.return_value.run.return_value = [_make_chunk()]
            events = self._run(**self._default_kwargs(model="gpt-4o"))

        assert specific_provider.call_count == 1
        assert any("data: direct" in e for e in events)

    def test_uses_fallback_client_when_model_is_none(self):
        fallback = FakeLLMProvider(tokens=["auto"])
        with (
            patch("documents.selectors.get_document_by_id"),
            patch("query.services._get_pipeline") as mock_pipeline,
            patch("query.services._resolve_provider", return_value=fallback),
        ):
            mock_pipeline.return_value.run.return_value = [_make_chunk()]
            events = self._run(**self._default_kwargs(model=None))

        assert fallback.call_count == 1
        assert any("data: auto" in e for e in events)
