"""
Integration tests for GET /api/v1/health/

Requires Docker services (PostgreSQL, Redis) to be running.
"""

from unittest.mock import MagicMock, patch

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


@pytest.mark.django_db
class TestHealthEndpointUnhealthy:
    def test_health_returns_503_when_postgres_down(self):
        with patch("core.health.connection") as mock_conn:
            mock_conn.cursor.side_effect = Exception("connection refused")
            response = APIClient().get("/api/v1/health/")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert "error" in data["checks"]["postgres"]

    def test_health_returns_503_when_redis_down(self):
        import redis as redis_lib

        with patch("core.health.redis_lib.from_url") as mock_from_url:
            mock_client = MagicMock()
            mock_client.ping.side_effect = redis_lib.RedisError("connection refused")
            mock_from_url.return_value = mock_client
            response = APIClient().get("/api/v1/health/")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert "error" in data["checks"]["redis"]
