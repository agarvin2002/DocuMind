"""
DocuMind root URL configuration.

  /admin/             → Django admin
  /api/v1/health/     → health check
  /api/v1/documents/  → document upload and management
  /api/v1/query/      → question answering
  /api/v1/analysis/   → agent workflows
  /api/docs/          → Swagger UI (auto-generated)
"""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.permissions import AllowAny

from core.health import health_check

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/health/", health_check, name="health-check"),
    path("api/v1/", include("documents.urls")),
    path("api/v1/", include("query.urls")),
    path("api/v1/", include("analysis.urls")),
    # Schema and docs are open — no API key needed for portfolio visibility.
    path(
        "api/schema/",
        SpectacularAPIView.as_view(authentication_classes=[], permission_classes=[AllowAny]),
        name="schema",
    ),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(
            url_name="schema",
            authentication_classes=[],
            permission_classes=[AllowAny],
        ),
        name="swagger-ui",
    ),
]
