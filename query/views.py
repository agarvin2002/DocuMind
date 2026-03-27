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

from django.http import StreamingHttpResponse
from rest_framework.renderers import JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.throttles import QueryAskThrottle, QuerySearchThrottle
from documents.exceptions import DocumentNotFoundError
from query.exceptions import ModelNotAvailableError, NoRelevantChunksError
from query.serializers import (
    AskRequestSerializer,
    ChunkResultSerializer,
    SearchRequestSerializer,
)
from query.services import execute_ask, execute_search
from retrieval.reranker import RerankerError

logger = logging.getLogger(__name__)


class SearchView(APIView):
    """
    POST /api/v1/query/search/

    Accepts a query string and document ID, runs the full retrieval pipeline,
    and returns a ranked list of the most relevant text chunks.
    """

    throttle_classes = [QuerySearchThrottle]

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
        except RerankerError as e:
            logger.error(
                "Reranker failed during search", extra={"error_type": type(e).__name__}
            )
            return Response(
                {"detail": "Search ranking failed. Please try again."}, status=500
            )

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


class AskView(APIView):
    """
    POST /api/v1/query/ask/

    Accepts a query, document ID, optional k and model, then streams a
    grounded LLM answer back as Server-Sent Events (SSE).

    SSE event sequence:
        data: <token>          ← one per token, repeated until answer is complete
        event: citations
        data: [{...}, ...]     ← JSON array of Citation objects, sent once
        event: done
        data: [DONE]           ← signals the client to close the connection
    """

    throttle_classes = [QueryAskThrottle]

    def perform_content_negotiation(self, request, force=False):
        # Clients send Accept: text/event-stream for SSE but DRF only knows about
        # JSON renderers and raises NotAcceptable before the view method runs.
        # Override to always accept — the actual Content-Type is set on the
        # StreamingHttpResponse below. Error responses use JSONRenderer directly.
        return (JSONRenderer(), "application/json")

    def post(self, request: Request) -> StreamingHttpResponse | Response:
        # Step 1: validate the request body.
        serializer = AskRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        query = serializer.validated_data["query"]
        document_id = serializer.validated_data["document_id"]
        k = serializer.validated_data["k"]
        model = serializer.validated_data["model"]

        logger.info(
            "Ask request received",
            extra={
                "document_id": str(document_id),
                "k": k,
                "model": model or "fallback",
            },
        )

        # Step 2 & 3: initialise the generator, catch pre-stream errors.
        # These errors are raised before any token is yielded — normal HTTP responses.
        try:
            event_stream = execute_ask(
                query=query,
                document_id=document_id,
                k=k,
                model=model,
            )
        except DocumentNotFoundError as e:
            return Response({"detail": str(e)}, status=e.http_status_code)
        except ModelNotAvailableError as e:
            return Response({"detail": str(e)}, status=e.http_status_code)
        except NoRelevantChunksError as e:
            return Response({"detail": str(e)}, status=e.http_status_code)
        except RerankerError:
            logger.error("Reranker failed during ask retrieval")
            return Response(
                {"detail": "Retrieval ranking failed. Please try again."}, status=500
            )

        # Step 4: stream the response.
        response = StreamingHttpResponse(
            streaming_content=event_stream,
            content_type="text/event-stream",
        )
        # Tell clients and proxies not to cache or buffer the stream.
        response["Cache-Control"] = "no-cache"
        # Tell nginx not to buffer — without this, nginx holds the entire stream
        # in memory before forwarding it, defeating SSE completely.
        response["X-Accel-Buffering"] = "no"
        return response
