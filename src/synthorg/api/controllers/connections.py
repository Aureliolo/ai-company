"""Connections API controller.

CRUD endpoints for the external service connection catalog,
including on-demand health checks.
"""

from typing import Any

from litestar import Controller, delete, get, patch, post
from litestar.datastructures import State  # noqa: TC002
from litestar.params import Parameter

from synthorg.api.dto import ApiResponse
from synthorg.api.errors import (
    ApiValidationError,
    ConflictError,
    NotFoundError,
)
from synthorg.api.guards import require_read_access, require_write_access
from synthorg.integrations.connections.catalog import _UNSET
from synthorg.integrations.connections.models import (
    Connection,
    ConnectionType,
    HealthReport,
)
from synthorg.integrations.errors import (
    ConnectionNotFoundError,
    DuplicateConnectionError,
    InvalidConnectionAuthError,
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
        """Create a new connection.

        Validates required fields and connection type before
        delegating to the catalog so clients get a structured
        400 instead of a 500 on malformed payloads.
        """
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            msg = "Field 'name' is required and must be a non-empty string"
            raise ApiValidationError(msg)
        # Persist the canonical trimmed form so "  github  " and
        # "github" cannot become two distinct identities and so the
        # /{name} routes consistently address the stored row.
        name = name.strip()

        connection_type_raw = data.get("connection_type")
        if not isinstance(connection_type_raw, str) or not connection_type_raw:
            msg = "Field 'connection_type' is required"
            raise ApiValidationError(msg)
        try:
            connection_type = ConnectionType(connection_type_raw)
        except ValueError as exc:
            msg = f"Unknown connection_type '{connection_type_raw}'"
            raise ApiValidationError(msg) from exc

        credentials = data.get("credentials", {})
        if not isinstance(credentials, dict):
            msg = "Field 'credentials' must be an object"
            raise ApiValidationError(msg)

        metadata = data.get("metadata")
        if metadata is not None and not isinstance(metadata, dict):
            msg = "Field 'metadata' must be an object if provided"
            raise ApiValidationError(msg)

        health_check_enabled = data.get("health_check_enabled", True)
        if not isinstance(health_check_enabled, bool):
            msg = "Field 'health_check_enabled' must be a boolean"
            raise ApiValidationError(msg)

        catalog = state["app_state"].connection_catalog
        try:
            conn = await catalog.create(
                name=name,
                connection_type=connection_type,
                auth_method=data.get("auth_method", "api_key"),
                credentials=credentials,
                base_url=data.get("base_url"),
                metadata=metadata,
                health_check_enabled=health_check_enabled,
            )
        except DuplicateConnectionError as exc:
            raise ConflictError(str(exc)) from exc
        except InvalidConnectionAuthError as exc:
            raise ApiValidationError(str(exc)) from exc
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
        # Validate PATCH field types at the boundary so malformed
        # payloads surface as a structured 400 instead of failing
        # inside the catalog / Pydantic model layer.
        if "base_url" in data:
            base_url_value = data["base_url"]
            if base_url_value is not None and not isinstance(base_url_value, str):
                msg = "Field 'base_url' must be a string or null"
                raise ApiValidationError(msg)
        metadata = data.get("metadata")
        if metadata is not None and not isinstance(metadata, dict):
            msg = "Field 'metadata' must be an object if provided"
            raise ApiValidationError(msg)
        health_check_enabled = data.get("health_check_enabled")
        if health_check_enabled is not None and not isinstance(
            health_check_enabled,
            bool,
        ):
            msg = "Field 'health_check_enabled' must be a boolean if provided"
            raise ApiValidationError(msg)

        catalog = state["app_state"].connection_catalog
        try:
            conn = await catalog.update(
                name,
                base_url=data.get("base_url", _UNSET),
                metadata=metadata,
                health_check_enabled=health_check_enabled,
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
        from synthorg.integrations.health.service import (  # noqa: PLC0415
            check_connection_health,
        )

        catalog = state["app_state"].connection_catalog
        try:
            report = await check_connection_health(catalog, name)
        except ConnectionNotFoundError as exc:
            raise NotFoundError(str(exc)) from exc
        await catalog.update_health(
            name,
            status=report.status,
            checked_at=report.checked_at,
        )
        return ApiResponse(data=report)
