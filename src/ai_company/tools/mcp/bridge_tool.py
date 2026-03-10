"""MCP bridge tool — wraps an MCP server tool as a ``BaseTool``.

Each ``MCPBridgeTool`` instance represents a single tool discovered
from an MCP server, bridging MCP protocol calls into the internal
tool system.
"""

from typing import TYPE_CHECKING, Any

from ai_company.core.enums import ToolCategory
from ai_company.observability import get_logger
from ai_company.observability.events.mcp import (
    MCP_CACHE_HIT,
    MCP_INVOKE_START,
)
from ai_company.tools.base import BaseTool, ToolExecutionResult
from ai_company.tools.mcp.result_mapper import map_call_tool_result

if TYPE_CHECKING:
    from ai_company.tools.mcp.cache import MCPResultCache
    from ai_company.tools.mcp.client import MCPClient
    from ai_company.tools.mcp.models import MCPToolInfo

logger = get_logger(__name__)


class MCPBridgeTool(BaseTool):
    """Bridge between an MCP server tool and the internal tool system.

    Constructs a ``BaseTool`` whose ``execute`` delegates to an MCP
    server via ``MCPClient``. An optional ``MCPResultCache`` avoids
    redundant remote calls for identical invocations.

    Args:
        tool_info: Discovered MCP tool metadata.
        client: Connected MCP client for the server.
        cache: Optional result cache.
    """

    def __init__(
        self,
        *,
        tool_info: MCPToolInfo,
        client: MCPClient,
        cache: MCPResultCache | None = None,
    ) -> None:
        super().__init__(
            name=f"mcp_{tool_info.server_name}_{tool_info.name}",
            description=tool_info.description,
            parameters_schema=tool_info.input_schema or None,
            category=ToolCategory.MCP,
        )
        self._client = client
        self._tool_info = tool_info
        self._cache = cache

    @property
    def tool_info(self) -> MCPToolInfo:
        """The underlying MCP tool metadata."""
        return self._tool_info

    async def execute(
        self,
        *,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        """Execute the MCP tool via the client.

        Checks the cache first (if available). On cache miss,
        invokes the remote tool and stores the result.

        Args:
            arguments: Tool invocation arguments.

        Returns:
            Mapped ``ToolExecutionResult``.
        """
        if self._cache is not None:
            cached = self._cache.get(
                self._tool_info.name,
                arguments,
            )
            if cached is not None:
                logger.debug(
                    MCP_CACHE_HIT,
                    tool_name=self._tool_info.name,
                    server=self._tool_info.server_name,
                )
                return cached

        logger.debug(
            MCP_INVOKE_START,
            tool=self._tool_info.name,
            server=self._tool_info.server_name,
        )
        raw = await self._client.call_tool(
            self._tool_info.name,
            arguments,
        )
        result = map_call_tool_result(raw)

        if self._cache is not None:
            self._cache.put(
                self._tool_info.name,
                arguments,
                result,
            )

        return result
