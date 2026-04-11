"""Slack API health check."""

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


class SlackHealthCheck:
    """Health check via ``auth.test`` on the Slack API."""

    async def check(self, connection: Connection) -> HealthReport:
        """Verify the Slack token is valid via auth.test."""
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(
                    "https://slack.com/api/auth.test",
                    headers={
                        "Authorization": "Bearer placeholder",
                    },
                )
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if data.get("ok"):
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
            return HealthReport(
                connection_name=connection.name,
                status=ConnectionStatus.UNHEALTHY,
                latency_ms=elapsed,
                error_detail=f"Slack auth.test: {data.get('error', 'unknown')}",
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
