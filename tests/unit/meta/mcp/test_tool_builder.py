"""Unit tests for MCP tool builder helpers."""

import pytest
from pydantic import ValidationError

from synthorg.meta.mcp.tool_builder import (
    admin_tool,
    read_tool,
    tool_def,
    write_tool,
)

pytestmark = pytest.mark.unit


class TestToolDef:
    """Tests for the generic tool_def builder."""

    def test_name_convention(self) -> None:
        t = tool_def("tasks", "list", "List tasks")
        assert t.name == "synthorg_tasks_list"

    def test_default_capability_is_read(self) -> None:
        t = tool_def("tasks", "list", "List tasks")
        assert t.capability == "tasks:read"

    def test_custom_capability_action(self) -> None:
        t = tool_def("tasks", "create", "Create task", capability_action="write")
        assert t.capability == "tasks:write"

    def test_handler_key_matches_name(self) -> None:
        t = tool_def("tasks", "list", "List tasks")
        assert t.handler_key == "synthorg_tasks_list"

    def test_empty_parameters(self) -> None:
        t = tool_def("tasks", "list", "List tasks")
        assert t.parameters == {
            "type": "object",
            "properties": {},
        }

    def test_with_properties(self) -> None:
        t = tool_def(
            "tasks",
            "list",
            "List tasks",
            {"status": {"type": "string"}},
        )
        assert "status" in t.parameters["properties"]

    def test_with_required(self) -> None:
        t = tool_def(
            "tasks",
            "get",
            "Get task",
            {"task_id": {"type": "string"}},
            required=("task_id",),
        )
        assert t.parameters["required"] == ["task_id"]

    def test_no_required_omits_field(self) -> None:
        t = tool_def("tasks", "list", "List tasks")
        assert "required" not in t.parameters


class TestReadTool:
    """Tests for read_tool shorthand."""

    def test_capability_is_read(self) -> None:
        t = read_tool("agents", "list", "List agents")
        assert t.capability == "agents:read"

    def test_name_convention(self) -> None:
        t = read_tool("agents", "get", "Get agent")
        assert t.name == "synthorg_agents_get"


class TestWriteTool:
    """Tests for write_tool shorthand."""

    def test_capability_is_write(self) -> None:
        t = write_tool("agents", "create", "Create agent")
        assert t.capability == "agents:write"

    def test_with_required_properties(self) -> None:
        t = write_tool(
            "tasks",
            "create",
            "Create task",
            {"title": {"type": "string"}},
            required=("title",),
        )
        assert t.parameters["required"] == ["title"]
        assert t.capability == "tasks:write"


class TestAdminTool:
    """Tests for admin_tool shorthand."""

    def test_capability_is_admin(self) -> None:
        t = admin_tool("settings", "update", "Update settings")
        assert t.capability == "settings:admin"

    def test_name_convention(self) -> None:
        t = admin_tool("backup", "create", "Create backup")
        assert t.name == "synthorg_backup_create"


class TestToolDefValidation:
    """Tests for invalid inputs that should be rejected by validators."""

    def test_uppercase_domain_rejected(self) -> None:
        with pytest.raises(ValidationError, match="synthorg_"):
            tool_def("Tasks", "list", "List tasks")

    def test_uppercase_action_rejected(self) -> None:
        with pytest.raises(ValidationError, match="synthorg_"):
            tool_def("tasks", "List", "List tasks")

    def test_empty_domain_rejected(self) -> None:
        with pytest.raises(ValidationError):
            tool_def("", "list", "List tasks")

    def test_empty_action_rejected(self) -> None:
        with pytest.raises(ValidationError):
            tool_def("tasks", "", "List tasks")

    def test_domain_with_spaces_rejected(self) -> None:
        with pytest.raises(ValidationError, match="synthorg_"):
            tool_def("my tasks", "list", "List tasks")

    def test_domain_starting_with_digit_rejected(self) -> None:
        with pytest.raises(ValidationError, match="synthorg_"):
            tool_def("1tasks", "list", "List tasks")
