"""Connections API controller.

CRUD endpoints for the external service connection catalog,
including on-demand health checks.
"""

from datetime import UTC, datetime
from typing import Any

from litestar import Controller, delete, get, patch, post
from litestar.datastructures import State  # noqa: TC002
from litestar.params import Parameter

from synthorg.api.dto import ApiResponse
from synthorg.api.errors import NotFoundError
from synthorg.api.guards import require_read_access, require_write_access
from synthorg.integrations.connections.catalog import _UNSET
from synthorg.integrations.connections.models import (
    Connection,
    HealthReport,
)
from synthorg.integrations.errors import (
    ConnectionNotFoundError,
    DuplicateConnectionError,
)
from synthorg.observability import get_logger

logger = get_logger(__name__)


class ConnectionsController(Controller):
    """CRUD and health endpoints for external connections."""

    path = "/api/v1/connections"
    tags = ["Integrations"]  # noqa: RUF012

    @get(
        "/",
        guards=[require_read_access],
        summary="List all connections",
    )
    async def list_connections(
        self,
        state: State,
    ) -> ApiResponse[tuple[Connection, ...]]:
        """List all connections in the catalog."""
        catalog = state["app_state"].connection_catalog
        connections = await catalog.list_all()
        return ApiResponse(data=connections)

    @get(
        "/{name:str}",
        guards=[require_read_access],
        summary="Get a connection by name",
    )
    async def get_connection(
        self,
        state: State,
        name: str = Parameter(description="Connection name"),
    ) -> ApiResponse[Connection]:
        """Get a single connection by name."""
        catalog = state["app_state"].connection_catalog
        conn = await catalog.get(name)
        if conn is None:
            msg = f"Connection '{name}' not found"
            raise NotFoundError(msg) from None
        return ApiResponse(data=conn)

    @post(
        "/",
        guards=[require_write_access],
        summary="Create a connection",
    )
    async def create_connection(
        self,
        state: State,
        data: dict[str, Any],
    ) -> ApiResponse[Connection]:
        """Create a new connection."""
        from synthorg.api.errors import ConflictError  # noqa: PLC0415
        from synthorg.integrations.connections.models import (  # noqa: PLC0415
            ConnectionType,
        )

        catalog = state["app_state"].connection_catalog
        try:
            conn = await catalog.create(
                name=data["name"],
                connection_type=ConnectionType(data["connection_type"]),
                auth_method=data.get("auth_method", "api_key"),
                credentials=data.get("credentials", {}),
                base_url=data.get("base_url"),
                metadata=data.get("metadata"),
                health_check_enabled=data.get(
                    "health_check_enabled",
                    True,
                ),
            )
        except DuplicateConnectionError as exc:
            raise ConflictError(str(exc)) from exc
        return ApiResponse(data=conn)

    @patch(
        "/{name:str}",
        guards=[require_write_access],
        summary="Update a connection",
    )
    async def update_connection(
        self,
        state: State,
        name: str,
        data: dict[str, Any],
    ) -> ApiResponse[Connection]:
        """Update mutable fields of a connection."""
        catalog = state["app_state"].connection_catalog
        try:
            conn = await catalog.update(
                name,
                base_url=data.get("base_url", _UNSET),
                metadata=data.get("metadata"),
                health_check_enabled=data.get("health_check_enabled"),
            )
        except ConnectionNotFoundError as exc:
            raise NotFoundError(str(exc)) from exc
        return ApiResponse(data=conn)

    @delete(
        "/{name:str}",
        guards=[require_write_access],
        summary="Delete a connection",
        status_code=200,
    )
    async def delete_connection(
        self,
        state: State,
        name: str,
    ) -> ApiResponse[None]:
        """Delete a connection and its secrets."""
        catalog = state["app_state"].connection_catalog
        try:
            await catalog.delete(name)
        except ConnectionNotFoundError as exc:
            raise NotFoundError(str(exc)) from exc
        return ApiResponse(data=None)

    @get(
        "/{name:str}/health",
        guards=[require_read_access],
        summary="Check connection health",
    )
    async def check_health(
        self,
        state: State,
        name: str,
    ) -> ApiResponse[HealthReport]:
        """Run an on-demand health check for a connection."""
        from synthorg.integrations.health.prober import (  # noqa: PLC0415
            _CHECK_REGISTRY,
        )

        catalog = state["app_state"].connection_catalog
        conn = await catalog.get(name)
        if conn is None:
            msg = f"Connection '{name}' not found"
            raise NotFoundError(msg) from None

        checker = _CHECK_REGISTRY.get(conn.connection_type)
        if checker is None:
            report = HealthReport(
                connection_name=conn.name,
                status=conn.health_status,
                error_detail="No health checker for this type",
                checked_at=datetime.now(UTC),
            )
            return ApiResponse(data=report)

        report = await checker.check(conn)
        await catalog.update_health(
            name,
            status=report.status,
            checked_at=report.checked_at,
        )
        return ApiResponse(data=report)
