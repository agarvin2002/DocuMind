"""
retrieval/vector_store.py — pgvector query interface for semantic search.

Phase 3 adds the read side: similarity search against stored chunk embeddings.
Chunk persistence (write side) lives in documents/services.py as
save_document_chunks() — it belongs there because DocumentChunk is a
documents model and all ORM writes on it are documents service operations.

Usage (Phase 3, not yet implemented):
    from retrieval.vector_store import search_chunks
"""
