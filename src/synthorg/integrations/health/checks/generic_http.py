"""Generic HTTP health check."""

import time
from datetime import UTC, datetime

import httpx

from synthorg.integrations.connections.models import (
    Connection,
    ConnectionStatus,
    HealthReport,
)
from synthorg.observability import get_logger
from synthorg.observability.events.integrations import (
    HEALTH_CHECK_FAILED,
    HEALTH_CHECK_PASSED,
)

logger = get_logger(__name__)

_TIMEOUT = 10.0


class GenericHttpHealthCheck:
    """Health check via HTTP HEAD to the connection's base URL."""

    async def check(self, connection: Connection) -> HealthReport:
        """Execute a HEAD request against ``connection.base_url``."""
        if not connection.base_url:
            return HealthReport(
                connection_name=connection.name,
                status=ConnectionStatus.UNKNOWN,
                error_detail="No base_url configured",
                checked_at=datetime.now(UTC),
            )
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.head(connection.base_url)
            elapsed = (time.monotonic() - start) * 1000
            if resp.status_code < 400:  # noqa: PLR2004
                logger.debug(
                    HEALTH_CHECK_PASSED,
                    connection_name=connection.name,
                    latency_ms=elapsed,
                )
                return HealthReport(
                    connection_name=connection.name,
                    status=ConnectionStatus.HEALTHY,
                    latency_ms=elapsed,
                    checked_at=datetime.now(UTC),
                )
            logger.debug(
                HEALTH_CHECK_FAILED,
                connection_name=connection.name,
                status_code=resp.status_code,
            )
            return HealthReport(
                connection_name=connection.name,
                status=ConnectionStatus.UNHEALTHY,
                latency_ms=elapsed,
                error_detail=f"HTTP {resp.status_code}",
                checked_at=datetime.now(UTC),
            )
        except httpx.HTTPError as exc:
            elapsed = (time.monotonic() - start) * 1000
            logger.debug(
                HEALTH_CHECK_FAILED,
                connection_name=connection.name,
                error=str(exc),
            )
            return HealthReport(
                connection_name=connection.name,
                status=ConnectionStatus.UNHEALTHY,
                latency_ms=elapsed,
                error_detail=str(exc),
                checked_at=datetime.now(UTC),
            )
