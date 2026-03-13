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
