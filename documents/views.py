"""
documents/views.py — API views for document upload and status retrieval.
"""

import logging
import os

from django.db import transaction
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.throttles import DocumentUploadThrottle
from documents.exceptions import DocumentNotFoundError, DocumentUploadError
from documents.selectors import get_document_by_id
from documents.serializers import DocumentSerializer, DocumentUploadSerializer
from documents.services import create_document, trigger_ingestion

logger = logging.getLogger(__name__)


class DocumentUploadView(APIView):
    """POST /api/v1/documents/ — accept a PDF upload and queue ingestion."""

    parser_classes = [MultiPartParser]
    throttle_classes = [DocumentUploadThrottle]

    def post(self, request: Request) -> Response:
        serializer = DocumentUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated = serializer.validated_data
        uploaded_file = validated["file"]
        original_filename = uploaded_file.name
        file_type = os.path.splitext(original_filename)[1].lower()

        try:
            doc = create_document(
                file=uploaded_file,
                title=validated["title"],
                original_filename=original_filename,
                file_type=file_type,
                api_key=request.auth,
            )
            # Queue the Celery task only after the DB transaction commits.
            # Without on_commit, a Redis crash between the INSERT and the
            # apply_async call leaves the document permanently stuck in PENDING
            # with no worker ever processing it.
            transaction.on_commit(lambda: trigger_ingestion(doc.id))
        except DocumentUploadError as e:
            return Response({"detail": str(e)}, status=e.http_status_code)

        logger.info(
            "Document upload accepted",
            extra={"document_id": str(doc.id), "original_filename": original_filename},
        )
        return Response(DocumentSerializer(doc).data, status=status.HTTP_201_CREATED)


class DocumentDetailView(APIView):
    """GET /api/v1/documents/{document_id}/ — return document metadata and status."""

    def get(self, request: Request, document_id) -> Response:
        try:
            doc = get_document_by_id(document_id, api_key=request.auth)
        except DocumentNotFoundError as e:
            return Response({"detail": str(e)}, status=e.http_status_code)

        return Response(DocumentSerializer(doc).data, status=status.HTTP_200_OK)
