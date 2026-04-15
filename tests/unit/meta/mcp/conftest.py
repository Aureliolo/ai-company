"""Shared fixtures and helpers for MCP unit tests."""

import pytest

from synthorg.meta.mcp.registry import DomainToolRegistry, MCPToolDef


def make_tool(
    name: str = "synthorg_test_get",
    capability: str = "test:read",
    **overrides: object,
) -> MCPToolDef:
    """Create a minimal MCPToolDef for testing.

    Args:
        name: Tool name.
        capability: Capability tag.
        **overrides: Override any MCPToolDef field.
    """
    defaults: dict[str, object] = {
        "name": name,
        "description": "A test tool",
        "parameters": {"type": "object", "properties": {}},
        "capability": capability,
        "handler_key": name,
    }
    defaults.update(overrides)
    return MCPToolDef(**defaults)  # type: ignore[arg-type]


def registry_with(*tools: MCPToolDef) -> DomainToolRegistry:
    """Create a frozen registry populated with the given tools."""
    registry = DomainToolRegistry()
    for t in tools:
        registry.register(t)
    registry.freeze()
    return registry


@pytest.fixture
def empty_registry() -> DomainToolRegistry:
    """Return a fresh empty frozen registry."""
    registry = DomainToolRegistry()
    registry.freeze()
    return registry
