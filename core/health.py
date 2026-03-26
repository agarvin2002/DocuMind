"""
Health check endpoint — GET /api/v1/health/

Returns 200 with service status when all dependencies are reachable.
Used by Docker health checks and load balancer readiness probes.
"""

import logging
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version

import redis as redis_lib
from django.conf import settings
from django.db import connection
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

logger = logging.getLogger(__name__)


def _get_version() -> str:
    try:
        return pkg_version("documind")
    except PackageNotFoundError:
        return "0.1.0"


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def health_check(request):
    """Returns 200 OK when healthy, 503 when any dependency is unreachable."""
    logger.debug("Health check requested")
    checks = {}
    all_healthy = True

    # PostgreSQL
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["postgres"] = "ok"
        logger.debug("PostgreSQL: ok")
    except Exception as e:  # noqa: BLE001
        checks["postgres"] = f"error: {e}"
        all_healthy = False
        logger.error(
            "PostgreSQL health check failed",
            extra={"error": str(e), "error_type": type(e).__name__},
        )

    # Redis — r initialised to None so finally is safe if from_url() raises.
    r = None
    try:
        r = redis_lib.from_url(
            settings.CELERY_BROKER_URL,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        r.ping()
        checks["redis"] = "ok"
        logger.debug("Redis: ok")
    except redis_lib.RedisError as e:
        checks["redis"] = f"error: {e}"
        all_healthy = False
        logger.error("Redis health check failed: %s", e)
    finally:
        if r is not None:
            r.close()

    if all_healthy:
        logger.info("Health check passed — all systems ok")
    else:
        logger.warning("Health check failed — degraded: %s", checks)

    response_status = (
        status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    )

    return Response(
        {
            "status": "healthy" if all_healthy else "unhealthy",
            "checks": checks,
            "version": _get_version(),
        },
        status=response_status,
    )
