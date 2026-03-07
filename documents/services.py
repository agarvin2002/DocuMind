"""
Documents app — services (write operations).

Views must never access the database directly; they call services instead.
Services own all create/update/delete logic and may dispatch Celery tasks.

Phase 2 will implement:
    create_document(file, title) -> Document
    trigger_ingestion(document_id) -> None
    delete_document(document_id) -> None
    get_document_status(document_id) -> Document.Status
"""
