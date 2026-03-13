"""
query/views.py — HTTP views for the query app.

Follows the project view pattern:
    1. Validate request with serializer → 400 if invalid
    2. Call service function
    3. Catch known exceptions → return their http_status_code
    4. Return serialized response

Views never touch the database directly or import from retrieval/.
All business logic lives in query/services.py.
"""

import logging

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from documents.exceptions import DocumentNotFoundError
from query.serializers import ChunkResultSerializer, SearchRequestSerializer
from query.services import NoRelevantChunksError, execute_search

logger = logging.getLogger(__name__)


class SearchView(APIView):
    """
    POST /api/v1/query/search/

    Accepts a query string and document ID, runs the full retrieval pipeline,
    and returns a ranked list of the most relevant text chunks.
    """

    def post(self, request: Request) -> Response:
        # Step 1: validate the request body.
        serializer = SearchRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        query = serializer.validated_data["query"]
        document_id = serializer.validated_data["document_id"]
        k = serializer.validated_data["k"]

        # Step 2 & 3: call the service, catch known errors.
        try:
            results = execute_search(query=query, document_id=document_id, k=k)
        except DocumentNotFoundError as e:
            return Response({"detail": str(e)}, status=e.http_status_code)
        except NoRelevantChunksError as e:
            return Response({"detail": str(e)}, status=e.http_status_code)

        # Step 4: return the response.
        return Response(
            {
                "query": query,
                "document_id": str(document_id),
                "result_count": len(results),
                "results": ChunkResultSerializer(results, many=True).data,
            },
            status=200,
        )
