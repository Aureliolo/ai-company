"""Shared health check helper.

Provides ``check_connection_health`` used by both the per-connection
endpoint on ``ConnectionsController`` and the aggregate endpoint on
``IntegrationHealthController``.
"""

from datetime import UTC, datetime

from synthorg.integrations.connections.catalog import ConnectionCatalog  # noqa: TC001
from synthorg.integrations.connections.models import ConnectionStatus
from synthorg.integrations.health.models import HealthReport
from synthorg.integrations.health.prober import _CHECK_REGISTRY
from synthorg.observability import get_logger
from synthorg.observability.events.integrations import HEALTH_CHECK_FAILED

logger = get_logger(__name__)


async def check_connection_health(
    catalog: ConnectionCatalog,
    name: str,
) -> HealthReport:
    """Run an on-demand health check for a single connection.

    Args:
        catalog: The connection catalog.
        name: Connection name.

    Returns:
        A ``HealthReport`` with the check result.

    Raises:
        ConnectionNotFoundError: If the connection does not exist.
    """
    conn = await catalog.get_or_raise(name)
    checker = _CHECK_REGISTRY.get(conn.connection_type)
    now = datetime.now(UTC)

    if checker is None:
        return HealthReport(
            connection_name=conn.name,
            status=conn.health_status,
            error_detail="No health checker for this type",
            checked_at=now,
        )

    try:
        return await checker.check(conn)
    except Exception as exc:
        logger.warning(
            HEALTH_CHECK_FAILED,
            connection_name=name,
            error=str(exc),
            exc_info=True,
        )
        return HealthReport(
            connection_name=conn.name,
            status=ConnectionStatus.UNHEALTHY,
            error_detail=str(exc),
            checked_at=now,
        )
