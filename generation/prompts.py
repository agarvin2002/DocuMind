from __future__ import annotations

from generation.constants import CHARS_PER_TOKEN
from retrieval.schemas import ChunkSearchResult

PROMPT_VERSION = "v1"

_PROMPTS: dict[str, str] = {
    "v1": (
        "You are DocuMind, a precise document analysis assistant.\n"
        "Answer the user's question using ONLY the provided document excerpts.\n"
        "- Cite sources inline as [1], [2] etc. — each number maps to the excerpt index.\n"
        "- If the excerpts do not contain the answer, say so explicitly.\n"
        "- Never fabricate information not present in the excerpts."
    ),
}


def get_system_prompt(version: str = PROMPT_VERSION) -> str:
    """Return the system prompt for the given version."""
    if version not in _PROMPTS:
        raise ValueError(f"Unknown prompt version: {version!r}. Available: {list(_PROMPTS)}")
    return _PROMPTS[version]


def estimate_token_count(text: str) -> int:
    """Rough token estimate: chars / CHARS_PER_TOKEN. Dependency-free."""
    return len(text) // CHARS_PER_TOKEN


def build_context_block(chunks: list[ChunkSearchResult]) -> str:
    """
    Format retrieved chunks as a numbered excerpt list for the LLM.

    Uses parent_text (the larger context window chunk) — NOT child_text.
    child_text is used only for retrieval scoring; parent_text is what the LLM reasons over.

    Output format:
        [1]
        Page 3
        <parent_text>

        [2]
        Page 7
        <parent_text>
        ...
    """
    lines: list[str] = []
    for i, chunk in enumerate(chunks, start=1):
        lines.append(f"[{i}]")
        lines.append(f"Page {chunk.page_number}")
        lines.append(chunk.parent_text)
        lines.append("")
    return "\n".join(lines).rstrip()


def build_user_message(
    query: str,
    chunks: list[ChunkSearchResult],
    *,
    max_context_tokens: int,
) -> str:
    """
    Assemble the full user message: context block + question.

    If the context block exceeds max_context_tokens, drops the lowest-scored
    chunks first (list is already sorted by score descending from the pipeline).
    This prevents context_length_exceeded errors from the LLM API.
    """
    included = _truncate_chunks(chunks, max_context_tokens=max_context_tokens)
    context = build_context_block(included)
    return f"Document excerpts:\n\n{context}\n\nQuestion: {query}"


def _truncate_chunks(
    chunks: list[ChunkSearchResult],
    *,
    max_context_tokens: int,
) -> list[ChunkSearchResult]:
    """
    Return the largest prefix of chunks that fits within max_context_tokens.
    Drops from the end (lowest-scored) first.
    """
    included: list[ChunkSearchResult] = []
    running_tokens = 0

    for chunk in chunks:
        chunk_tokens = estimate_token_count(chunk.parent_text)
        if running_tokens + chunk_tokens > max_context_tokens:
            break
        included.append(chunk)
        running_tokens += chunk_tokens

    return included
