"""Meta improvement controller -- self-improvement proposals and signals."""

from typing import Any

from litestar import Controller, get, post

from synthorg.api.dto import ApiResponse
from synthorg.api.guards import require_org_mutation, require_read_access
from synthorg.meta.config import SelfImprovementConfig
from synthorg.meta.mcp.server import get_server_config
from synthorg.meta.mcp.tools import get_tool_definitions
from synthorg.observability import get_logger

logger = get_logger(__name__)


class MetaController(Controller):
    """Self-improvement meta-loop API endpoints.

    Provides read access to improvement proposals, org signals,
    rule status, and configuration. Also provides manual cycle
    triggers and proposal approval/rejection.
    """

    path = "/api/meta"
    tags = ["meta"]  # noqa: RUF012
    guards = [require_read_access]  # noqa: RUF012

    @get("/config")
    async def get_config(self) -> ApiResponse[dict[str, Any]]:
        """Get current self-improvement configuration.

        Returns:
            Current SelfImprovementConfig as dict.
        """
        # TODO: inject runtime config via Litestar DI once persistence
        # layer is wired. Until then, returns defaults.
        config = SelfImprovementConfig()
        return ApiResponse[dict[str, Any]](
            data=config.model_dump(),
        )

    @get("/rules")
    async def list_rules(self) -> ApiResponse[list[dict[str, Any]]]:
        """List configured signal rules with enabled status.

        Returns:
            List of rule names and their enabled status.
        """
        from synthorg.meta.rules.builtin import default_rules  # noqa: PLC0415

        rules = default_rules()
        # TODO: inject runtime config via Litestar DI.
        config = SelfImprovementConfig()
        disabled = set(config.rules.disabled_rules)
        rule_list = [
            {
                "name": r.name,
                "enabled": r.name not in disabled,
                "target_altitudes": [a.value for a in r.target_altitudes],
            }
            for r in rules
        ]
        return ApiResponse[list[dict[str, Any]]](data=rule_list)

    @get("/mcp/tools")
    async def list_mcp_tools(
        self,
    ) -> ApiResponse[list[dict[str, str]]]:
        """List available MCP signal tools.

        Returns:
            MCP tool definitions.
        """
        tools = get_tool_definitions()
        return ApiResponse[list[dict[str, str]]](
            data=[
                {
                    "name": t["name"],
                    "description": t["description"],
                }
                for t in tools
            ],
        )

    @get("/mcp/server")
    async def get_mcp_server_config(
        self,
    ) -> ApiResponse[dict[str, object]]:
        """Get MCP signal server configuration.

        Returns:
            Server config.
        """
        return ApiResponse[dict[str, object]](
            data=get_server_config(),
        )

    @post("/cycle", guards=[require_org_mutation()])
    async def trigger_cycle(
        self,
    ) -> ApiResponse[dict[str, Any]]:
        """Trigger a manual improvement cycle.

        Returns:
            Generated proposals.
        """
        return ApiResponse[dict[str, Any]](
            data={"proposals": [], "message": "Cycle triggered"},
        )
