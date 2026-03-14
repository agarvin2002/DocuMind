"""
retrieval/protocols.py — Port interfaces for all retrieval dependencies.

Defines structural Protocols so RetrievalPipeline depends on abstractions,
not on Django, Redis, or any specific model library.
"""

import uuid
from typing import Protocol

from retrieval.schemas import ChunkSearchResult


class QueryEmbedderPort(Protocol):
    def embed_single(self, text: str) -> list[float]: ...


class VectorSearchPort(Protocol):
    def __call__(
        self,
        embedding: list[float],
        document_id: uuid.UUID,
        k: int,
    ) -> list[ChunkSearchResult]: ...


class KeywordSearchPort(Protocol):
    def __call__(
        self,
        query: str,
        document_id: uuid.UUID,
        k: int,
    ) -> list[ChunkSearchResult]: ...


class RerankerPort(Protocol):
    def rerank(
        self,
        query: str,
        candidates: list[ChunkSearchResult],
    ) -> list[ChunkSearchResult]: ...
