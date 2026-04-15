"""Quality domain MCP tools.

Covers quality, reviews, and evaluation config versions.
"""

from typing import TYPE_CHECKING

from synthorg.meta.mcp.tool_builder import PAGINATION_PROPERTIES, read_tool, write_tool

if TYPE_CHECKING:
    from synthorg.meta.mcp.registry import MCPToolDef

QUALITY_TOOLS: tuple[MCPToolDef, ...] = (
    # --- Quality ---
    read_tool("quality", "get_summary", "Get quality summary for the organization."),
    read_tool(
        "quality",
        "get_agent_quality",
        "Get quality metrics for a specific agent.",
        {
            "agent_name": {"type": "string", "description": "Agent name"},
        },
        required=("agent_name",),
    ),
    read_tool(
        "quality",
        "list_scores",
        "List quality score records.",
        {
            "agent_name": {"type": "string", "description": "Filter by agent"},
            **PAGINATION_PROPERTIES,
        },
    ),
    # --- Reviews ---
    read_tool(
        "reviews",
        "list",
        "List task reviews.",
        {
            "task_id": {"type": "string", "description": "Filter by task"},
            "reviewer": {"type": "string", "description": "Filter by reviewer"},
            **PAGINATION_PROPERTIES,
        },
    ),
    read_tool(
        "reviews",
        "get",
        "Get a review by ID.",
        {
            "review_id": {"type": "string", "description": "Review UUID"},
        },
        required=("review_id",),
    ),
    write_tool(
        "reviews",
        "create",
        "Create a task review.",
        {
            "task_id": {"type": "string", "description": "Task being reviewed"},
            "score": {
                "type": "number",
                "description": "Review score (0-1)",
                "minimum": 0,
                "maximum": 1,
            },
            "feedback": {"type": "string", "description": "Review feedback"},
        },
        required=("task_id", "score"),
    ),
    write_tool(
        "reviews",
        "update",
        "Update a review.",
        {
            "review_id": {"type": "string", "description": "Review UUID"},
            "updates": {"type": "object", "description": "Fields to update"},
        },
        required=("review_id", "updates"),
    ),
    # --- Evaluation config versions ---
    read_tool(
        "evaluation_versions",
        "list",
        "List evaluation config versions.",
        PAGINATION_PROPERTIES,
    ),
    read_tool(
        "evaluation_versions",
        "get",
        "Get a specific evaluation config version.",
        {
            "version_num": {"type": "integer", "description": "Version number"},
        },
        required=("version_num",),
    ),
)
