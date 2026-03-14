"""
retrieval/schemas.py — Shared data transfer object for retrieval results.

ChunkSearchResult flows through every retrieval component (vector, keyword,
hybrid fusion, reranker) as the universal result type.
"""

from dataclasses import dataclass


@dataclass
class ChunkSearchResult:
    chunk_id: str
    document_id: str
    document_title: str
    chunk_index: int
    child_text: str
    parent_text: str
    page_number: int
    score: float
