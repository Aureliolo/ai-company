"""Slack API health check."""

import time
from datetime import UTC, datetime

import httpx

from synthorg.integrations.connections.catalog import ConnectionCatalog  # noqa: TC001
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
    """Health check via ``auth.test`` on the Slack API.

    Args:
        catalog: Connection catalog used to resolve the Slack token
            at check time. ``None`` means the checker cannot
            authenticate (returns UNKNOWN).
    """

    def __init__(self, catalog: ConnectionCatalog | None = None) -> None:
        self._catalog = catalog

    def bind_catalog(self, catalog: ConnectionCatalog) -> None:
        """Bind a catalog after construction.

        The check registry is instantiated at import time before the
        catalog exists, so it is injected afterwards via
        :func:`bind_health_check_catalog`.
        """
        self._catalog = catalog

    async def check(self, connection: Connection) -> HealthReport:
        """Verify the Slack token is valid via auth.test."""
        now = datetime.now(UTC)
        if self._catalog is None:
            logger.warning(
                HEALTH_CHECK_FAILED,
                connection_name=connection.name,
                error="catalog not bound, cannot fetch token",
            )
            return HealthReport(
                connection_name=connection.name,
                status=ConnectionStatus.UNKNOWN,
                error_detail="catalog not bound",
                checked_at=now,
            )

        credentials = await self._catalog.get_credentials(connection.name)
        token = credentials.get("token")
        if not token:
            logger.warning(
                HEALTH_CHECK_FAILED,
                connection_name=connection.name,
                error="missing Slack token",
            )
            return HealthReport(
                connection_name=connection.name,
                status=ConnectionStatus.UNHEALTHY,
                error_detail="missing Slack token",
                checked_at=now,
            )

        return await self._call_auth_test(connection, token)

    async def _call_auth_test(
        self,
        connection: Connection,
        token: str,
    ) -> HealthReport:
        """Execute the ``auth.test`` call and interpret the response."""
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(
                    "https://slack.com/api/auth.test",
                    headers={"Authorization": f"Bearer {token}"},
                )
        except httpx.HTTPError as exc:
            elapsed = (time.monotonic() - start) * 1000
            logger.warning(
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

        elapsed = (time.monotonic() - start) * 1000
        if resp.is_error:
            return HealthReport(
                connection_name=connection.name,
                status=ConnectionStatus.UNHEALTHY,
                latency_ms=elapsed,
                error_detail=f"Slack HTTP {resp.status_code}",
                checked_at=datetime.now(UTC),
            )
        try:
            data = resp.json()
        except ValueError as exc:
            logger.warning(
                HEALTH_CHECK_FAILED,
                connection_name=connection.name,
                error=f"invalid JSON: {exc}",
            )
            return HealthReport(
                connection_name=connection.name,
                status=ConnectionStatus.UNHEALTHY,
                latency_ms=elapsed,
                error_detail="invalid JSON from Slack",
                checked_at=datetime.now(UTC),
            )
        if data.get("ok"):
            logger.info(
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
