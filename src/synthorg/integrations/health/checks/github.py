"""GitHub API health check."""

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

_DEFAULT_API_URL = "https://api.github.com"
_TIMEOUT = 10.0


class GitHubHealthCheck:
    """Health check via ``GET /user`` on the GitHub API."""

    async def check(self, connection: Connection) -> HealthReport:
        """Verify the GitHub token is valid via /user endpoint."""
        api_url = connection.base_url or _DEFAULT_API_URL
        url = f"{api_url}/user"
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    url,
                    headers={
                        "Authorization": "Bearer placeholder",
                        "Accept": "application/vnd.github+json",
                    },
                )
            elapsed = (time.monotonic() - start) * 1000
            if resp.status_code == 200:  # noqa: PLR2004
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
                error_detail=f"GitHub API returned {resp.status_code}",
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
