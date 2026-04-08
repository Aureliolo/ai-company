"""Tests for the diagram generator tool."""

import pytest

from synthorg.core.enums import ActionType, ToolCategory
from synthorg.tools.design.diagram_generator import DiagramGeneratorTool


@pytest.mark.unit
class TestDiagramGeneratorTool:
    """Tests for DiagramGeneratorTool."""

    def test_category_is_design(self) -> None:
        tool = DiagramGeneratorTool()
        assert tool.category == ToolCategory.DESIGN

    def test_action_type_is_docs_write(self) -> None:
        tool = DiagramGeneratorTool()
        assert tool.action_type == ActionType.DOCS_WRITE

    def test_name(self) -> None:
        tool = DiagramGeneratorTool()
        assert tool.name == "diagram_generator"

    async def test_execute_mermaid_flowchart(self) -> None:
        tool = DiagramGeneratorTool()
        result = await tool.execute(
            arguments={
                "diagram_type": "flowchart",
                "description": "A --> B\nB --> C",
            }
        )
        assert not result.is_error
        assert "flowchart TD" in result.content
        assert "A --> B" in result.content
        assert result.metadata["diagram_type"] == "flowchart"
        assert result.metadata["output_format"] == "mermaid"

    async def test_execute_mermaid_sequence(self) -> None:
        tool = DiagramGeneratorTool()
        result = await tool.execute(
            arguments={
                "diagram_type": "sequence",
                "description": "Alice->>Bob: Hello",
            }
        )
        assert not result.is_error
        assert "sequenceDiagram" in result.content

    async def test_execute_mermaid_class(self) -> None:
        tool = DiagramGeneratorTool()
        result = await tool.execute(
            arguments={
                "diagram_type": "class",
                "description": "Animal <|-- Duck",
            }
        )
        assert not result.is_error
        assert "classDiagram" in result.content

    async def test_execute_mermaid_state(self) -> None:
        tool = DiagramGeneratorTool()
        result = await tool.execute(
            arguments={
                "diagram_type": "state",
                "description": "[*] --> Active",
            }
        )
        assert not result.is_error
        assert "stateDiagram-v2" in result.content

    async def test_execute_with_title(self) -> None:
        tool = DiagramGeneratorTool()
        result = await tool.execute(
            arguments={
                "diagram_type": "flowchart",
                "description": "A --> B",
                "title": "My Diagram",
            }
        )
        assert not result.is_error
        assert "title: My Diagram" in result.content

    async def test_execute_graphviz(self) -> None:
        tool = DiagramGeneratorTool()
        result = await tool.execute(
            arguments={
                "diagram_type": "flowchart",
                "description": "A -> B",
                "output_format": "graphviz",
            }
        )
        assert not result.is_error
        assert "digraph" in result.content
        assert "A -> B" in result.content

    async def test_execute_graphviz_with_title(self) -> None:
        tool = DiagramGeneratorTool()
        result = await tool.execute(
            arguments={
                "diagram_type": "flowchart",
                "description": "A -> B",
                "output_format": "graphviz",
                "title": "Test",
            }
        )
        assert not result.is_error
        assert 'label="Test"' in result.content

    async def test_execute_invalid_diagram_type(self) -> None:
        tool = DiagramGeneratorTool()
        result = await tool.execute(
            arguments={
                "diagram_type": "invalid",
                "description": "test",
            }
        )
        assert result.is_error
        assert "Invalid diagram_type" in result.content

    async def test_execute_invalid_output_format(self) -> None:
        tool = DiagramGeneratorTool()
        result = await tool.execute(
            arguments={
                "diagram_type": "flowchart",
                "description": "test",
                "output_format": "pdf",
            }
        )
        assert result.is_error
        assert "Invalid output_format" in result.content

    async def test_execute_architecture_uses_graph_in_graphviz(
        self,
    ) -> None:
        tool = DiagramGeneratorTool()
        result = await tool.execute(
            arguments={
                "diagram_type": "architecture",
                "description": "A -- B",
                "output_format": "graphviz",
            }
        )
        assert not result.is_error
        assert result.content.startswith("graph ")

    def test_parameters_schema_requires_type_and_description(
        self,
    ) -> None:
        tool = DiagramGeneratorTool()
        schema = tool.parameters_schema
        assert schema is not None
        assert "diagram_type" in schema["required"]
        assert "description" in schema["required"]
