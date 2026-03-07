"""
Integration tests for GET /api/v1/health/

Requires Docker services (PostgreSQL, Redis) to be running.
"""

import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestHealthEndpoint:

    def test_health_endpoint_returns_200(self):
        response = APIClient().get("/api/v1/health/")
        assert response.status_code == 200

    def test_health_response_has_correct_shape(self):
        data = APIClient().get("/api/v1/health/").json()
        assert "status" in data
        assert "checks" in data
        assert "version" in data

    def test_health_reports_postgres_ok(self):
        data = APIClient().get("/api/v1/health/").json()
        assert data["checks"]["postgres"] == "ok"

    def test_health_reports_redis_ok(self):
        data = APIClient().get("/api/v1/health/").json()
        assert data["checks"]["redis"] == "ok"
