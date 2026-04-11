"""MCP catalog API controller.

Browse and install MCP servers from the bundled catalog.
"""

from typing import TYPE_CHECKING

from litestar import Controller, get
from litestar.datastructures import State  # noqa: TC002
from litestar.params import Parameter

from synthorg.api.dto import ApiResponse
from synthorg.api.guards import require_read_access
from synthorg.integrations.errors import CatalogEntryNotFoundError
from synthorg.observability import get_logger

if TYPE_CHECKING:
    from synthorg.integrations.connections.models import CatalogEntry

logger = get_logger(__name__)


class MCPCatalogController(Controller):
    """Browse and install MCP servers from the bundled catalog."""

    path = "/api/v1/integrations/mcp"
    tags = ["Integrations"]  # noqa: RUF012

    @get(
        "/catalog",
        guards=[require_read_access],
        summary="List all catalog entries",
    )
    async def browse_catalog(
        self,
        state: State,
    ) -> ApiResponse[tuple[CatalogEntry, ...]]:
        """List all curated MCP server entries."""
        service = state["app_state"].mcp_catalog_service
        entries = await service.browse()
        return ApiResponse(data=entries)

    @get(
        "/catalog/search",
        guards=[require_read_access],
        summary="Search catalog entries",
    )
    async def search_catalog(
        self,
        state: State,
        q: str = Parameter(description="Search query"),
    ) -> ApiResponse[tuple[CatalogEntry, ...]]:
        """Search catalog by name, description, or tags."""
        service = state["app_state"].mcp_catalog_service
        entries = await service.search(q)
        return ApiResponse(data=entries)

    @get(
        "/catalog/{entry_id:str}",
        guards=[require_read_access],
        summary="Get a catalog entry",
    )
    async def get_entry(
        self,
        state: State,
        entry_id: str,
    ) -> ApiResponse[CatalogEntry]:
        """Get a single catalog entry by ID."""
        from synthorg.api.errors import NotFoundError  # noqa: PLC0415

        service = state["app_state"].mcp_catalog_service
        try:
            entry = await service.get_entry(entry_id)
        except CatalogEntryNotFoundError as exc:
            raise NotFoundError(str(exc)) from exc
        return ApiResponse(data=entry)
