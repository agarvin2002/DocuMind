"""
query/protocols.py — structural interfaces for the query layer.

Follows the same pattern as agents/protocols.py: @runtime_checkable Protocol
so isinstance() checks work at runtime (useful for dependency injection assertions
in tests).
"""

import uuid
from typing import Protocol, runtime_checkable


@runtime_checkable
class SemanticCachePort(Protocol):
    """
    Contract for semantic cache implementations.

    execute_ask() depends on this protocol, never on SemanticCache directly,
    so tests can inject FakeSemanticCache without touching the real DB.
    """

    def lookup(
        self,
        query: str,
        document_id: uuid.UUID,
    ) -> dict | None:
        """
        Return cached answer_json if a semantically similar query for this
        document exists within the TTL, or None on a cache miss.

        Must never raise — on any error, return None (treat as a miss).
        """
        ...

    def store(
        self,
        query: str,
        document_id: uuid.UUID,
        answer_json: dict,
    ) -> None:
        """
        Embed the query and persist a new SemanticCacheEntry.

        Must never raise — cache write failures are non-fatal.
        """
        ...
