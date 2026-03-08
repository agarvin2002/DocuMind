"""
documents/urls.py — URL routes for the documents app.

Mounted at /api/v1/ in core/urls.py, so full paths are:
    POST /api/v1/documents/
    GET  /api/v1/documents/<uuid>/
"""

from django.urls import path

from documents.views import DocumentDetailView, DocumentUploadView

app_name = "documents"

urlpatterns = [
    path("documents/", DocumentUploadView.as_view(), name="upload"),
    path("documents/<uuid:document_id>/", DocumentDetailView.as_view(), name="detail"),
]
