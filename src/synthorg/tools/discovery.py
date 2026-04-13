"""Built-in discovery tools for progressive tool disclosure.

Three read-only tools always available to agents:

- ``list_tools`` -- returns L1 metadata for all permitted tools
- ``load_tool`` -- returns L2 body for a specific tool
- ``load_tool_resource`` -- returns a specific L3 resource

Discovery tools signal load/unload state changes via
``ToolExecutionResult.metadata`` keys that the
``DisclosureMiddleware`` observes.
"""

import json
from typing import Any, Protocol, runtime_checkable

from synthorg.core.enums import ToolCategory
from synthorg.core.tool_disclosure import (  # noqa: TC001
    ToolL1Metadata,
    ToolL2Body,
    ToolL3Resource,
)
from synthorg.observability import get_logger

from .base import BaseTool, ToolExecutionResult

logger = get_logger(__name__)

# ── Disclosure manager protocol ──────────────────────────────────


@runtime_checkable
class ToolDisclosureManager(Protocol):
    """Protocol for discovery tools to query tool metadata.

    Implemented by ``ToolInvoker`` to break the circular
    dependency between discovery tools and the registry.
    """

    def get_l1_summaries(self) -> tuple[ToolL1Metadata, ...]:
        """Return L1 metadata for all permitted tools."""
        ...

    def get_l2_body(self, tool_name: str) -> ToolL2Body | None:
        """Return L2 body for a specific tool, or ``None``."""
        ...

    def get_l3_resource(
        self,
        tool_name: str,
        resource_id: str,
    ) -> ToolL3Resource | None:
        """Return a specific L3 resource, or ``None``."""
        ...


# ── Discovery tools ──────────────────────────────────────────────

_DISCOVERY_NAMES: frozenset[str] = frozenset(
    {"list_tools", "load_tool", "load_tool_resource"},
)
"""Names of the three built-in discovery tools."""


class ListToolsTool(BaseTool):
    """Return L1 metadata for all permitted tools.

    Always available regardless of agent access level.
    """

    def __init__(self, manager: ToolDisclosureManager) -> None:
        super().__init__(
            name="list_tools",
            description="List all available tools with brief descriptions",
            category=ToolCategory.MEMORY,
            action_type="memory:read",
        )
        self._manager = manager

    async def execute(
        self,
        *,
        arguments: dict[str, Any],  # noqa: ARG002
    ) -> ToolExecutionResult:
        """Return JSON array of L1 metadata."""
        summaries = self._manager.get_l1_summaries()
        payload = [
            {
                "name": s.name,
                "short_description": s.short_description,
                "category": s.category,
                "typical_cost_tier": s.typical_cost_tier,
            }
            for s in summaries
        ]
        return ToolExecutionResult(
            content=json.dumps(payload, indent=2),
            metadata={"tool_count": len(payload)},
        )


class LoadToolTool(BaseTool):
    """Load a tool's L2 body (full specification).

    Always available regardless of agent access level.
    Sets ``metadata["should_load_tool"]`` to signal the
    ``DisclosureMiddleware`` to mark the tool as loaded.
    """

    def __init__(self, manager: ToolDisclosureManager) -> None:
        super().__init__(
            name="load_tool",
            description="Load the full specification for a tool",
            parameters_schema={
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "description": "Name of the tool to load",
                    },
                },
                "required": ["tool_name"],
            },
            category=ToolCategory.MEMORY,
            action_type="memory:read",
        )
        self._manager = manager

    async def execute(
        self,
        *,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        """Return L2 body JSON for the requested tool."""
        tool_name: str = arguments["tool_name"]
        l2 = self._manager.get_l2_body(tool_name)
        if l2 is None:
            return ToolExecutionResult(
                content=f"Tool {tool_name!r} not found or has no L2 body",
                is_error=True,
            )
        payload = {
            "name": tool_name,
            "full_description": l2.full_description,
            "parameters": dict(l2.parameter_schema),
            "usage_examples": list(l2.usage_examples),
            "failure_modes": list(l2.failure_modes),
        }
        return ToolExecutionResult(
            content=json.dumps(payload, indent=2),
            metadata={"should_load_tool": tool_name},
        )


class LoadToolResourceTool(BaseTool):
    """Fetch a specific L3 resource for a tool.

    Always available regardless of agent access level.
    Sets ``metadata["should_load_resource"]`` to signal the
    ``DisclosureMiddleware``.
    """

    def __init__(self, manager: ToolDisclosureManager) -> None:
        super().__init__(
            name="load_tool_resource",
            description="Load a specific advanced resource for a tool",
            parameters_schema={
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "description": "Name of the tool",
                    },
                    "resource_id": {
                        "type": "string",
                        "description": "Identifier of the resource",
                    },
                },
                "required": ["tool_name", "resource_id"],
            },
            category=ToolCategory.MEMORY,
            action_type="memory:read",
        )
        self._manager = manager

    async def execute(
        self,
        *,
        arguments: dict[str, Any],
    ) -> ToolExecutionResult:
        """Return L3 resource content."""
        tool_name: str = arguments["tool_name"]
        resource_id: str = arguments["resource_id"]
        resource = self._manager.get_l3_resource(tool_name, resource_id)
        if resource is None:
            return ToolExecutionResult(
                content=(f"Resource {resource_id!r} not found for tool {tool_name!r}"),
                is_error=True,
            )
        return ToolExecutionResult(
            content=resource.content,
            metadata={
                "should_load_resource": (tool_name, resource_id),
                "content_type": resource.content_type,
                "size_bytes": resource.size_bytes,
            },
        )


def build_discovery_tools(
    manager: ToolDisclosureManager,
) -> tuple[BaseTool, ...]:
    """Create the three built-in discovery tools.

    Args:
        manager: Disclosure manager providing L1/L2/L3 queries.

    Returns:
        Tuple of ``(ListToolsTool, LoadToolTool, LoadToolResourceTool)``.
    """
    return (
        ListToolsTool(manager),
        LoadToolTool(manager),
        LoadToolResourceTool(manager),
    )
