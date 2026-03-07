"""
Documents app — selectors (read operations).

All database queries are centralised here rather than scattered across views
and services. Services handle writes; selectors handle reads.

Phase 2 will implement:
    get_document_by_id(document_id) -> Document
    list_documents(status=None) -> QuerySet[Document]
    get_chunks_for_document(document_id) -> QuerySet[DocumentChunk]
"""
