"""MCP tool definition builder helpers.

Provides concise builder functions for creating ``MCPToolDef`` instances.
Each builder sets the capability tag automatically from domain and action
type, enforcing the ``synthorg_{domain}_{action}`` naming convention.
"""

from typing import Any

from synthorg.meta.mcp.registry import MCPToolDef


def _make_parameters(
    properties: dict[str, Any] | None = None,
    *,
    required: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Build a JSON Schema ``object`` for tool parameters.

    Args:
        properties: Property definitions (``None`` for empty).
        required: Required property names.

    Returns:
        JSON Schema dict.
    """
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties or {},
    }
    if required:
        schema["required"] = list(required)
    return schema


def tool_def(  # noqa: PLR0913
    domain: str,
    action: str,
    description: str,
    properties: dict[str, Any] | None = None,
    *,
    required: tuple[str, ...] = (),
    capability_action: str = "read",
) -> MCPToolDef:
    """Build an MCP tool definition with naming convention enforcement.

    Args:
        domain: Domain slug (e.g. ``"tasks"``).
        action: Action slug (e.g. ``"list"``, ``"create"``).
        description: Human-readable tool description.
        properties: JSON Schema properties for parameters.
        required: Required parameter names.
        capability_action: Capability action tag (``"read"`` or ``"write"``).

    Returns:
        Frozen ``MCPToolDef`` instance.
    """
    name = f"synthorg_{domain}_{action}"
    capability = f"{domain}:{capability_action}"
    handler_key = name
    return MCPToolDef(
        name=name,
        description=description,
        parameters=_make_parameters(properties, required=required),
        capability=capability,
        handler_key=handler_key,
    )


def read_tool(
    domain: str,
    action: str,
    description: str,
    properties: dict[str, Any] | None = None,
    *,
    required: tuple[str, ...] = (),
) -> MCPToolDef:
    """Build a read-only MCP tool definition.

    Shorthand for ``tool_def(..., capability_action="read")``.

    Args:
        domain: Domain slug.
        action: Action slug.
        description: Human-readable description.
        properties: JSON Schema properties.
        required: Required parameter names.

    Returns:
        Frozen ``MCPToolDef`` with ``read`` capability.
    """
    return tool_def(
        domain,
        action,
        description,
        properties,
        required=required,
        capability_action="read",
    )


def write_tool(
    domain: str,
    action: str,
    description: str,
    properties: dict[str, Any] | None = None,
    *,
    required: tuple[str, ...] = (),
) -> MCPToolDef:
    """Build a write MCP tool definition.

    Shorthand for ``tool_def(..., capability_action="write")``.

    Args:
        domain: Domain slug.
        action: Action slug.
        description: Human-readable description.
        properties: JSON Schema properties.
        required: Required parameter names.

    Returns:
        Frozen ``MCPToolDef`` with ``write`` capability.
    """
    return tool_def(
        domain,
        action,
        description,
        properties,
        required=required,
        capability_action="write",
    )


def admin_tool(
    domain: str,
    action: str,
    description: str,
    properties: dict[str, Any] | None = None,
    *,
    required: tuple[str, ...] = (),
) -> MCPToolDef:
    """Build an admin MCP tool definition.

    Shorthand for ``tool_def(..., capability_action="admin")``.

    Args:
        domain: Domain slug.
        action: Action slug.
        description: Human-readable description.
        properties: JSON Schema properties.
        required: Required parameter names.

    Returns:
        Frozen ``MCPToolDef`` with ``admin`` capability.
    """
    return tool_def(
        domain,
        action,
        description,
        properties,
        required=required,
        capability_action="admin",
    )
