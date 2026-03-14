"""
query/serializers.py — Request validation and response shaping for the search endpoint.

SearchRequestSerializer validates inbound POST data before it reaches the service layer.
SearchResponseSerializer converts ChunkSearchResult dataclass objects into JSON-ready dicts.

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


class SearchResponseSerializer(serializers.Serializer):
    """Shapes the full response body for a successful search."""

    query = serializers.CharField()
    document_id = serializers.UUIDField()
    result_count = serializers.IntegerField()
    results = ChunkResultSerializer(many=True)
