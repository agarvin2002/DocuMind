from pydantic import BaseModel


class Citation(BaseModel):
    """A single source that grounds a claim in the LLM's answer."""

    chunk_id: str
    document_title: str
    page_number: int
    quote: str  # The exact sentence from parent_text that supports the answer


class GeneratedAnswer(BaseModel):
    """The complete output of one LLM generation call."""

    answer: str  # Full answer text with inline [1], [2] citation markers
    citations: list[Citation]
    model_used: str  # e.g. "gpt-4o" or "claude-sonnet-4-5"
    prompt_version: (
        str  # e.g. "v1" — ties this answer to the exact prompt that produced it
    )
    input_token_count: int
    output_token_count: int
