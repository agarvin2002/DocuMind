"""
Documents admin — registers models in Django's /admin/ dashboard.

This lets us visually inspect, edit, and debug documents during development
without writing any extra API endpoints.
"""

from django.contrib import admin

from documents.models import Document, DocumentChunk


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    # Columns shown in the list view
    list_display = ["title", "status", "file_type", "file_size", "chunk_count", "created_at"]
    # Filters in the right sidebar
    list_filter = ["status", "file_type"]
    # Search bar (searches these fields)
    search_fields = ["title", "original_filename"]
    # Newest first
    ordering = ["-created_at"]
    # Make status and file_type non-editable after creation
    readonly_fields = ["id", "created_at", "updated_at", "chunk_count"]


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ["document", "chunk_index", "page_number", "created_at"]
    list_filter = ["document"]
    search_fields = ["child_text", "parent_text"]
    ordering = ["document", "chunk_index"]
    readonly_fields = ["id", "created_at", "embedding"]
