"""Generic CRUD handler factory for MCP tools.

Provides factory functions that create handler functions for common
CRUD operations, reducing boilerplate across domain handler modules.
"""

import json
from typing import Any

from synthorg.observability import get_logger
from synthorg.observability.events.mcp import (
    MCP_SERVER_INVOKE_START,
)

logger = get_logger(__name__)


def make_placeholder_handler(tool_name: str) -> Any:
    """Create a placeholder handler that returns a not-implemented message.

    Used for tools whose service layer integration is pending.
    The handler returns a structured JSON response indicating the
    tool is registered but not yet wired to the service layer.

    Args:
        tool_name: Tool name for the message.

    Returns:
        Async handler function.
    """

    async def handler(
        *,
        app_state: Any,  # noqa: ARG001
        arguments: dict[str, Any],
    ) -> str:
        logger.debug(
            MCP_SERVER_INVOKE_START,
            tool_name=tool_name,
            placeholder=True,
        )
        return json.dumps(
            {
                "status": "not_implemented",
                "tool": tool_name,
                "message": (
                    f"Tool {tool_name!r} is registered but its service "
                    f"layer handler is not yet implemented."
                ),
                "arguments_received": arguments,
            }
        )

    return handler


def make_handlers_for_tools(
    tool_names: tuple[str, ...],
) -> dict[str, Any]:
    """Create placeholder handlers for a set of tool names.

    Args:
        tool_names: Tuple of tool name strings.

    Returns:
        Dict mapping tool names to placeholder handlers.
    """
    return {name: make_placeholder_handler(name) for name in tool_names}
