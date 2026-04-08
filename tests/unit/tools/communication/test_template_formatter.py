"""Tests for the template formatter tool."""

import pytest

from synthorg.core.enums import ActionType, ToolCategory
from synthorg.tools.communication.template_formatter import (
    TemplateFormatterTool,
)


@pytest.mark.unit
class TestTemplateFormatterTool:
    """Tests for TemplateFormatterTool."""

    def test_category_is_communication(self) -> None:
        tool = TemplateFormatterTool()
        assert tool.category == ToolCategory.COMMUNICATION

    def test_action_type_is_code_read(self) -> None:
        tool = TemplateFormatterTool()
        assert tool.action_type == ActionType.CODE_READ

    def test_name(self) -> None:
        tool = TemplateFormatterTool()
        assert tool.name == "template_formatter"

    async def test_execute_simple_template(self) -> None:
        tool = TemplateFormatterTool()
        result = await tool.execute(
            arguments={
                "template": "Hello {{ name }}!",
                "variables": {"name": "Alice"},
            }
        )
        assert not result.is_error
        assert result.content == "Hello Alice!"

    async def test_execute_multiple_variables(self) -> None:
        tool = TemplateFormatterTool()
        result = await tool.execute(
            arguments={
                "template": "{{ greeting }} {{ name }}, balance: {{ amount }}",
                "variables": {
                    "greeting": "Hi",
                    "name": "Bob",
                    "amount": "$100",
                },
            }
        )
        assert not result.is_error
        assert result.content == "Hi Bob, balance: $100"

    async def test_execute_invalid_template_syntax(self) -> None:
        tool = TemplateFormatterTool()
        result = await tool.execute(
            arguments={
                "template": "Hello {{ name",
                "variables": {"name": "test"},
            }
        )
        assert result.is_error
        assert "Invalid template syntax" in result.content

    async def test_execute_undefined_variable(self) -> None:
        tool = TemplateFormatterTool()
        result = await tool.execute(
            arguments={
                "template": "Hello {{ name }}!",
                "variables": {},
            }
        )
        # Jinja2 renders undefined as empty string by default
        assert not result.is_error
        assert result.content == "Hello !"

    async def test_execute_with_format_metadata(self) -> None:
        tool = TemplateFormatterTool()
        result = await tool.execute(
            arguments={
                "template": "# {{ title }}",
                "variables": {"title": "Report"},
                "format": "markdown",
            }
        )
        assert not result.is_error
        assert result.metadata["format"] == "markdown"
        assert result.metadata["output_length"] == len("# Report")

    async def test_execute_invalid_format(self) -> None:
        tool = TemplateFormatterTool()
        result = await tool.execute(
            arguments={
                "template": "test",
                "variables": {},
                "format": "yaml",
            }
        )
        assert result.is_error
        assert "Invalid format" in result.content

    async def test_execute_html_template(self) -> None:
        tool = TemplateFormatterTool()
        result = await tool.execute(
            arguments={
                "template": "<h1>{{ title }}</h1><p>{{ body }}</p>",
                "variables": {"title": "Hello", "body": "World"},
                "format": "html",
            }
        )
        assert not result.is_error
        assert "<h1>Hello</h1>" in result.content

    async def test_jinja2_conditionals(self) -> None:
        tool = TemplateFormatterTool()
        result = await tool.execute(
            arguments={
                "template": "{% if urgent %}URGENT: {% endif %}{{ msg }}",
                "variables": {"urgent": True, "msg": "Server down"},
            }
        )
        assert not result.is_error
        assert result.content == "URGENT: Server down"

    async def test_jinja2_loop(self) -> None:
        tool = TemplateFormatterTool()
        result = await tool.execute(
            arguments={
                "template": "{% for item in items %}{{ item }} {% endfor %}",
                "variables": {"items": ["a", "b", "c"]},
            }
        )
        assert not result.is_error
        assert "a b c" in result.content

    async def test_sandbox_blocks_attribute_access(self) -> None:
        """SandboxedEnvironment prevents dangerous attribute access."""
        tool = TemplateFormatterTool()
        result = await tool.execute(
            arguments={
                "template": "{{ ''.__class__.__bases__ }}",
                "variables": {},
            }
        )
        # Sandbox should block or render safely (no class hierarchy)
        assert result.is_error or "__class__" not in result.content

    async def test_html_format_escapes_xss(self) -> None:
        """HTML format auto-escapes to prevent XSS."""
        tool = TemplateFormatterTool()
        result = await tool.execute(
            arguments={
                "template": "<p>{{ content }}</p>",
                "variables": {"content": "<script>alert(1)</script>"},
                "format": "html",
            }
        )
        assert not result.is_error
        assert "<script>" not in result.content
        assert "&lt;script&gt;" in result.content

    async def test_text_format_does_not_escape(self) -> None:
        """Text format passes through without HTML escaping."""
        tool = TemplateFormatterTool()
        result = await tool.execute(
            arguments={
                "template": "{{ content }}",
                "variables": {"content": "<b>bold</b>"},
                "format": "text",
            }
        )
        assert not result.is_error
        assert "<b>bold</b>" in result.content

    def test_parameters_schema_requires_template_and_variables(
        self,
    ) -> None:
        tool = TemplateFormatterTool()
        schema = tool.parameters_schema
        assert schema is not None
        assert "template" in schema["required"]
        assert "variables" in schema["required"]
