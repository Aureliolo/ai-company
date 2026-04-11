"""Connection health check protocol."""

from typing import Protocol, runtime_checkable

from synthorg.integrations.connections.models import (
    Connection,  # noqa: TC001
    HealthReport,  # noqa: TC001
)


@runtime_checkable
class ConnectionHealthCheck(Protocol):
    """Per-type health check implementation.

    Implementations must never raise -- always return a
    ``HealthReport`` with the appropriate status and error detail.
    """

    async def check(self, connection: Connection) -> HealthReport:
        """Execute a health check against the connection's endpoint.

        Args:
            connection: The connection to check.

        Returns:
            A ``HealthReport`` with status, latency, and error detail.
        """
        ...
