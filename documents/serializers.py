"""
documents/serializers.py — DRF serializers for document upload and retrieval.
"""

import os

from django.conf import settings
from rest_framework import serializers

from documents.models import Document

_ALLOWED_EXTENSIONS = {".pdf"}


def _max_upload_bytes() -> int:
    # Read from settings so the limit is configurable per environment without
    # a code change. Falls back to 50 MB if the setting is absent.
    mb = getattr(settings, "DOCUMIND_MAX_UPLOAD_SIZE_MB", 50)
    return mb * 1024 * 1024


class DocumentUploadSerializer(serializers.Serializer):
    """Validates a multipart file upload for POST /api/v1/documents/."""

    file = serializers.FileField()
    title = serializers.CharField(max_length=500, required=False, allow_blank=True)

    def validate_file(self, value):
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in _ALLOWED_EXTENSIONS:
            raise serializers.ValidationError(
                f"File type {ext!r} is not supported. "
                f"Allowed: {sorted(_ALLOWED_EXTENSIONS)}"
            )
        if value.size > _max_upload_bytes():
            max_mb = getattr(settings, "DOCUMIND_MAX_UPLOAD_SIZE_MB", 50)
            raise serializers.ValidationError(
                f"File size exceeds the maximum of {max_mb} MB"
            )
        return value

    def validate(self, data):
        # Default title to the filename stem when the client omits it.
        if not data.get("title"):
            data["title"] = os.path.splitext(data["file"].name)[0]
        return data


class DocumentSerializer(serializers.ModelSerializer):
    """Read serializer for GET /api/v1/documents/{id}/."""

    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "original_filename",
            "file_type",
            "file_size",
            "status",
            "error_message",
            "chunk_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
