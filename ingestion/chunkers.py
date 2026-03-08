"""
ingestion/chunkers.py — Split document text into hierarchical parent/child chunks.

Usage:
    from ingestion.chunkers import HierarchicalChunker, ChunkData

    chunker = HierarchicalChunker()
    chunks = chunker.chunk(pages)  # pages = [(1, "text"), (2, "text"), ...]
    # [ChunkData(chunk_index=0, child_text="...", parent_text="...", page_number=1), ...]
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ChunkData:
    """
    One chunk of a parsed document.

    child_text is embedded and indexed for retrieval (~128 tokens).
    parent_text is the wider context window sent to the LLM (~512 tokens).
    Both refer to the same passage — child is a sub-window of parent.
    """

    chunk_index: int
    child_text: str
    parent_text: str
    page_number: int  # 1-indexed page where this chunk starts


class HierarchicalChunker:
    """
    Produces overlapping child chunks with wider parent context windows.

    Tokenisation uses whitespace splitting — deterministic and dependency-free.
    The tradeoff is no stopword removal or stemming; retrieval quality benchmarks
    are deferred to Phase 3 where they can be measured and improved.
    """

    CHILD_TOKENS: int = 128
    PARENT_TOKENS: int = 512
    OVERLAP_TOKENS: int = 20

    def chunk(self, pages: list[tuple[int, str]]) -> list[ChunkData]:
        """
        Split pages into overlapping child/parent chunk pairs.

        Args:
            pages: List of (1-indexed page_number, text) tuples from a parser.

        Returns:
            List of ChunkData, one per child window. Empty list if all pages
            contain no text (image-only or blank document).
        """
        # Flatten all page text into a single token stream, tracking which
        # token belongs to which page so page_number can be assigned per chunk.
        all_tokens: list[str] = []
        token_pages: list[int] = []  # parallel list: page_number for each token

        for page_number, text in pages:
            tokens = text.split()
            all_tokens.extend(tokens)
            token_pages.extend([page_number] * len(tokens))

        if not all_tokens:
            logger.debug("Chunker received empty token stream — returning no chunks")
            return []

        chunks: list[ChunkData] = []
        step = self.CHILD_TOKENS - self.OVERLAP_TOKENS
        chunk_index = 0

        for child_start in range(0, len(all_tokens), step):
            child_end = child_start + self.CHILD_TOKENS
            child_tokens = all_tokens[child_start:child_end]

            if not child_tokens:
                break

            # Parent window is centred on the child window.
            # Clamp to document boundaries so we never go out of range.
            parent_half = self.PARENT_TOKENS // 2
            parent_start = max(0, child_start - parent_half)
            parent_end = min(
                len(all_tokens), child_start + self.CHILD_TOKENS + parent_half
            )
            parent_tokens = all_tokens[parent_start:parent_end]

            chunks.append(
                ChunkData(
                    chunk_index=chunk_index,
                    child_text=" ".join(child_tokens),
                    parent_text=" ".join(parent_tokens),
                    page_number=token_pages[child_start],
                )
            )
            chunk_index += 1

        logger.debug(
            "Chunking complete",
            extra={
                "total_tokens": len(all_tokens),
                "chunk_count": len(chunks),
                "child_size": self.CHILD_TOKENS,
                "overlap": self.OVERLAP_TOKENS,
            },
        )
        return chunks
