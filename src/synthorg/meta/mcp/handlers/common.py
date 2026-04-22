"""Generic CRUD handler factory for MCP tools.

Provides factory functions that create handler functions for common
CRUD operations, reducing boilerplate across domain handler modules.

The placeholder implementations below are the current state for all
19 domain handlers; real service-layer wiring is tracked in
``META-MCP-1`` (see docs). Every invocation emits a WARNING-level
``MCP_HANDLER_NOT_IMPLEMENTED`` event so operators can see which
placeholder tools are hit.
"""

import json
from typing import Any

from synthorg.observability import get_logger
from synthorg.observability.events.mcp import (
    MCP_HANDLER_NOT_IMPLEMENTED,
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
        logger.warning(
            MCP_HANDLER_NOT_IMPLEMENTED,
            tool_name=tool_name,
            follow_up_issue="META-MCP-1",
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
