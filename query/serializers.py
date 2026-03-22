"""
query/serializers.py — Request validation and response shaping for search and ask endpoints.

SearchRequestSerializer validates inbound POST data for /api/v1/query/search/.
AskRequestSerializer validates inbound POST data for /api/v1/query/ask/.
ChunkResultSerializer serializes individual ChunkSearchResult objects for the response body.

Usage:
    serializer = SearchRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    query = serializer.validated_data["query"]
"""

from rest_framework import serializers


class SearchRequestSerializer(serializers.Serializer):
    """Validates the POST body for /api/v1/query/search/."""

    query = serializers.CharField(
        min_length=1,
        max_length=1000,
        help_text="The search query string.",
    )
    document_id = serializers.UUIDField(
        help_text="UUID of the document to search within.",
    )
    k = serializers.IntegerField(
        default=10,
        min_value=1,
        max_value=50,
        help_text="Number of results to return. Defaults to 10.",
    )


class ChunkResultSerializer(serializers.Serializer):
    """Serializes a single ChunkSearchResult for the response body."""

    chunk_id = serializers.CharField()
    document_title = serializers.CharField()
    page_number = serializers.IntegerField()
    child_text = serializers.CharField()
    parent_text = serializers.CharField()
    score = serializers.FloatField()


class AskRequestSerializer(serializers.Serializer):
    """Validates the POST body for /api/v1/query/ask/."""

    query = serializers.CharField(
        min_length=1,
        max_length=1000,
        help_text="The question to answer.",
    )
    document_id = serializers.UUIDField(
        help_text="UUID of the document to answer from.",
    )
    k = serializers.IntegerField(
        default=5,
        min_value=1,
        max_value=20,
        help_text=(
            "Number of chunks to retrieve for context. Defaults to 5. "
            "Lower than search (10) — fewer chunks = tighter context = better answers."
        ),
    )
    model = serializers.CharField(
        required=False,
        default=None,
        allow_null=True,
        help_text=(
            "Model to use for generation. "
            "Examples: 'gpt-4o', 'claude-sonnet-4-5', "
            "'anthropic.claude-3-sonnet-20240229-v1:0', 'llama3.2'. "
            "Omit or set null to use the auto-fallback chain."
        ),
    )
