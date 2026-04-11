"""Integration health API controller.

Aggregate and per-connection health endpoints for the
external service connection catalog.
"""

import asyncio

from litestar import Controller, get
from litestar.datastructures import State  # noqa: TC002

from synthorg.api.dto import ApiResponse
from synthorg.api.errors import NotFoundError
from synthorg.api.guards import require_read_access
from synthorg.integrations.connections.catalog import ConnectionCatalog  # noqa: TC001
from synthorg.integrations.errors import ConnectionNotFoundError
from synthorg.integrations.health.models import HealthReport  # noqa: TC001
from synthorg.integrations.health.service import check_connection_health
from synthorg.observability import get_logger

logger = get_logger(__name__)


class IntegrationHealthController(Controller):
    """Aggregate and per-connection health checks."""

    path = "/api/v1/integrations/health"
    tags = ["Integrations"]  # noqa: RUF012

    @get(
        "/",
        guards=[require_read_access],
        summary="Aggregate health report across all connections",
    )
    async def aggregate_health(
        self,
        state: State,
    ) -> ApiResponse[tuple[HealthReport, ...]]:
        """Return cached health reports for all connections.

        Runs per-connection checks concurrently via
        ``asyncio.TaskGroup`` so total latency is bounded by the
        slowest check rather than the sum of all checks.
        """
        catalog: ConnectionCatalog = state["app_state"].connection_catalog
        connections = await catalog.list_all()
        if not connections:
            return ApiResponse(data=())

        async with asyncio.TaskGroup() as tg:
            tasks = [
                tg.create_task(check_connection_health(catalog, conn.name))
                for conn in connections
            ]
        reports = tuple(task.result() for task in tasks)
        return ApiResponse(data=reports)

    @get(
        "/{connection_name:str}",
        guards=[require_read_access],
        summary="Health report for a single connection",
    )
    async def single_health(
        self,
        state: State,
        connection_name: str,
    ) -> ApiResponse[HealthReport]:
        """Return the health report for one connection."""
        catalog = state["app_state"].connection_catalog
        try:
            report = await check_connection_health(
                catalog,
                connection_name,
            )
        except ConnectionNotFoundError as exc:
            raise NotFoundError(str(exc)) from exc
        return ApiResponse(data=report)
