"""
analysis/views.py — HTTP views for the analysis app.

Follows the project view pattern:
    1. Validate request with serializer → 400 if invalid
    2. Validate preconditions (documents exist) → 404 if not found
    3. Call service function, catch known exceptions → return their http_status_code
    4. Return serialized response

Views never touch the database directly.
All business logic lives in analysis/services.py and analysis/selectors.py.
"""

import logging

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from analysis.exceptions import AnalysisJobNotFoundError
from analysis.models import AnalysisJob
from analysis.selectors import get_cached_result, get_job_by_id
from analysis.serializers import AnalysisJobSerializer, AnalysisRequestSerializer
from analysis.services import create_analysis_job, dispatch_analysis_task
from core.throttles import AnalysisCreateThrottle
from documents.exceptions import DocumentNotFoundError
from documents.selectors import get_document_by_id

logger = logging.getLogger(__name__)


class AnalysisJobCreateView(APIView):
    """
    POST /api/v1/analysis/

    Validates all document IDs exist, creates an AnalysisJob (status=pending),
    dispatches a background Celery task, and returns 202 Accepted.

    The client should poll GET /api/v1/analysis/{job_id}/ until status=complete.
    """

    throttle_classes = [AnalysisCreateThrottle]

    def post(self, request: Request) -> Response:
        # Step 1: validate the request body.
        serializer = AnalysisRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        data = serializer.validated_data
        document_ids = data["document_ids"]

        # Step 2: validate all document IDs exist and belong to the caller.
        # Scoping by api_key prevents cross-key analysis of another user's documents.
        # Fail fast with a clear 404 rather than letting the Celery task fail silently.
        try:
            for doc_id in document_ids:
                get_document_by_id(doc_id, api_key=request.auth)
        except DocumentNotFoundError as exc:
            return Response({"detail": str(exc)}, status=exc.http_status_code)

        # Step 3: create the job and dispatch the background task.
        workflow_type = data.get("workflow_type") or AnalysisJob.WorkflowType.MULTI_HOP
        input_data = {
            "question": data["question"],
            "document_ids": [str(uid) for uid in document_ids],
            "workflow_type": workflow_type,
        }

        logger.info(
            "analysis_create_request",
            extra={"workflow_type": workflow_type, "document_count": len(document_ids)},
        )

        job, created = create_analysis_job(
            workflow_type=workflow_type, input_data=input_data
        )
        if created:
            dispatch_analysis_task(job)

        # Step 4: return the appropriate status code.
        # 202 Accepted — new job created and dispatched for async processing.
        # 200 OK       — deduplicated: returning an existing job, no new work queued.
        response_status = status.HTTP_202_ACCEPTED if created else status.HTTP_200_OK
        return Response(AnalysisJobSerializer(job).data, status=response_status)


class AnalysisJobDetailView(APIView):
    """
    GET /api/v1/analysis/{job_id}/

    Returns the current status of an analysis job.
    - status=pending/running → result_data is null
    - status=complete → result_data contains the full structured answer
    - status=failed → error_message explains why
    """

    def get(self, request: Request, job_id) -> Response:
        # Step 1: check Redis cache — completed jobs are served without a DB hit.
        # Guard: only use the cached value if it has the expected job shape.
        # An old-format entry (raw result_data without "status") is treated as a miss.
        cached = get_cached_result(str(job_id))
        if cached is not None and "status" in cached:
            return Response(cached, status=200)

        # Step 2: cache miss — fetch from DB.
        try:
            job = get_job_by_id(str(job_id))
        except AnalysisJobNotFoundError as exc:
            return Response({"detail": str(exc)}, status=exc.http_status_code)

        return Response(AnalysisJobSerializer(job).data, status=200)
