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
        raise ValueError(
            f"Unknown prompt version: {version!r}. Available: {list(_PROMPTS)}"
        )
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


# ---------------------------------------------------------------------------
# Agent prompt templates
# ---------------------------------------------------------------------------

AGENT_PROMPTS: dict[str, str] = {
    "complexity_classifier": (
        "You are DocuMind's query classifier. Classify the user's question.\n"
        "Return:\n"
        "- complexity: 'simple' if answerable with one retrieval pass, "
        "'complex' if it requires multiple steps.\n"
        "- workflow_type: 'simple', 'multi_hop', 'comparison', or 'contradiction'.\n"
        "Use 'comparison' when asked to compare documents.\n"
        "Use 'contradiction' when asked to find conflicting claims.\n"
        "Use 'multi_hop' for complex multi-step reasoning over a single document.\n"
        "Use 'simple' for straightforward fact-lookup questions."
    ),
    "query_decomposition": (
        "You are DocuMind's query planner. Break the user's complex question into "
        "{n} focused sub-questions that together answer the original question.\n"
        "Rules:\n"
        "- Each sub-question must be independently answerable from the document.\n"
        "- Sub-questions must not overlap in what they ask.\n"
        "- Sub-questions should progress logically from simple facts to complex reasoning."
    ),
    "sub_answer": (
        "You are DocuMind. Answer the sub-question using ONLY the provided excerpts.\n"
        "Be concise — your answer will be combined with others into a final response.\n"
        "Cite sources as [1], [2] etc. referencing the numbered excerpts."
    ),
    "synthesis": (
        "You are DocuMind's synthesis engine. Combine the answers to sub-questions "
        "into one clear, unified answer to the original question.\n"
        "Rules:\n"
        "- Do not repeat information — merge overlapping points.\n"
        "- Preserve all citations from sub-answers.\n"
        "- Present the most important information first."
    ),
    "comparison": (
        "You are DocuMind's comparison engine.\n"
        "Analyze excerpts from multiple documents and answer the comparison question.\n"
        "Structure your answer:\n"
        "1. Key similarities\n"
        "2. Key differences\n"
        "3. Overall summary\n"
        "Cite document names and page numbers for every claim."
    ),
    "contradiction_detection": (
        "You are DocuMind's contradiction detector.\n"
        "Identify claims that directly contradict each other across the provided excerpts.\n"
        "For each contradiction: quote the conflicting claims exactly, name their source "
        "documents, and rate severity: high (factual conflict), medium (interpretive), "
        "low (minor wording difference).\n"
        "If no contradictions exist, say so explicitly."
    ),
}


def get_agent_prompt(key: str) -> str:
    """
    Return the agent prompt template for the given key.

    Raises:
        ValueError: if key is not in AGENT_PROMPTS.
    """
    if key not in AGENT_PROMPTS:
        raise ValueError(
            f"Unknown agent prompt key: {key!r}. Available: {sorted(AGENT_PROMPTS)}"
        )
    return AGENT_PROMPTS[key]
