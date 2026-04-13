"""Tests for ToolInvoker disclosure-aware methods."""

from typing import Any

import pytest

from synthorg.core.enums import ToolAccessLevel, ToolCategory
from synthorg.tools.base import BaseTool, ToolExecutionResult
from synthorg.tools.invoker import ToolInvoker
from synthorg.tools.permissions import ToolPermissionChecker
from synthorg.tools.registry import ToolRegistry


class _FakeTool(BaseTool):
    """Minimal tool for invoker tests."""

    def __init__(
        self,
        *,
        name: str = "fake",
        description: str = "A fake tool",
        category: ToolCategory = ToolCategory.FILE_SYSTEM,
    ) -> None:
        super().__init__(
            name=name,
            description=description,
            category=category,
        )

    async def execute(self, *, arguments: dict[str, Any]) -> ToolExecutionResult:
        return ToolExecutionResult(content="ok")


def _build_invoker(
    *,
    tools: list[BaseTool] | None = None,
    checker: ToolPermissionChecker | None = None,
) -> ToolInvoker:
    """Build a ToolInvoker with given tools and optional permission checker."""
    if tools is None:
        tools = [
            _FakeTool(name="alpha", category=ToolCategory.FILE_SYSTEM),
            _FakeTool(name="beta", category=ToolCategory.WEB),
            _FakeTool(name="gamma", category=ToolCategory.DEPLOYMENT),
        ]
    registry = ToolRegistry(tools)
    return ToolInvoker(registry, permission_checker=checker)


# ── get_l1_summaries ────────────────────────────────────────────


@pytest.mark.unit
class TestGetL1Summaries:
    """Tests for ToolInvoker.get_l1_summaries()."""

    def test_no_checker_returns_all(self) -> None:
        invoker = _build_invoker()
        summaries = invoker.get_l1_summaries()
        assert len(summaries) == 3
        names = [s.name for s in summaries]
        assert names == ["alpha", "beta", "gamma"]

    def test_with_checker_filters(self) -> None:
        checker = ToolPermissionChecker(
            access_level=ToolAccessLevel.SANDBOXED,
        )
        invoker = _build_invoker(checker=checker)
        summaries = invoker.get_l1_summaries()
        names = {s.name for s in summaries}
        # SANDBOXED allows FILE_SYSTEM but not WEB or DEPLOYMENT
        assert "alpha" in names
        assert "beta" not in names
        assert "gamma" not in names


# ── get_loaded_definitions ──────────────────────────────────────


@pytest.mark.unit
class TestGetLoadedDefinitions:
    """Tests for ToolInvoker.get_loaded_definitions()."""

    def test_empty_loaded_returns_only_discovery(self) -> None:
        invoker = _build_invoker()
        defs = invoker.get_loaded_definitions(frozenset())
        names = {d.name for d in defs}
        # No tools loaded, no discovery tools registered,
        # so no definitions returned
        assert names == set()

    def test_loaded_tools_included(self) -> None:
        invoker = _build_invoker()
        defs = invoker.get_loaded_definitions(frozenset({"alpha", "beta"}))
        names = {d.name for d in defs}
        assert "alpha" in names
        assert "beta" in names
        assert "gamma" not in names

    def test_discovery_tool_names_always_included(self) -> None:
        tools = [
            _FakeTool(name="list_tools", category=ToolCategory.MEMORY),
            _FakeTool(name="load_tool", category=ToolCategory.MEMORY),
            _FakeTool(name="load_tool_resource", category=ToolCategory.MEMORY),
            _FakeTool(name="alpha", category=ToolCategory.FILE_SYSTEM),
        ]
        invoker = _build_invoker(tools=tools)
        defs = invoker.get_loaded_definitions(frozenset())
        names = {d.name for d in defs}
        assert "list_tools" in names
        assert "load_tool" in names
        assert "load_tool_resource" in names
        assert "alpha" not in names

    def test_loaded_plus_discovery(self) -> None:
        tools = [
            _FakeTool(name="list_tools", category=ToolCategory.MEMORY),
            _FakeTool(name="load_tool", category=ToolCategory.MEMORY),
            _FakeTool(name="load_tool_resource", category=ToolCategory.MEMORY),
            _FakeTool(name="alpha", category=ToolCategory.FILE_SYSTEM),
            _FakeTool(name="beta", category=ToolCategory.WEB),
        ]
        invoker = _build_invoker(tools=tools)
        defs = invoker.get_loaded_definitions(frozenset({"alpha"}))
        names = {d.name for d in defs}
        assert names == {"list_tools", "load_tool", "load_tool_resource", "alpha"}

    def test_sorted_by_name(self) -> None:
        tools = [
            _FakeTool(name="zebra", category=ToolCategory.FILE_SYSTEM),
            _FakeTool(name="aardvark", category=ToolCategory.FILE_SYSTEM),
        ]
        invoker = _build_invoker(tools=tools)
        defs = invoker.get_loaded_definitions(frozenset({"zebra", "aardvark"}))
        names = [d.name for d in defs]
        assert names == ["aardvark", "zebra"]
