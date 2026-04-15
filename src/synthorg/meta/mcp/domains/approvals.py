"""Approval domain MCP tools."""

from typing import TYPE_CHECKING

from synthorg.meta.mcp.tool_builder import (
    PAGINATION_PROPERTIES,
    read_tool,
    write_tool,
)

if TYPE_CHECKING:
    from synthorg.meta.mcp.registry import MCPToolDef

APPROVAL_TOOLS: tuple[MCPToolDef, ...] = (
    read_tool(
        "approvals",
        "list",
        "List approval items with optional filtering.",
        {
            "status": {"type": "string", "description": "Filter by approval status"},
            "risk_level": {"type": "string", "description": "Filter by risk level"},
            "action_type": {"type": "string", "description": "Filter by action type"},
            **PAGINATION_PROPERTIES,
        },
    ),
    read_tool(
        "approvals",
        "get",
        "Get an approval item by ID.",
        {
            "approval_id": {"type": "string", "description": "Approval UUID"},
        },
        required=("approval_id",),
    ),
    write_tool(
        "approvals",
        "create",
        "Create a new approval request.",
        {
            "action_type": {
                "type": "string",
                "description": "Type of action requiring approval",
            },
            "description": {
                "type": "string",
                "description": "Description of the proposed action",
            },
            "risk_level": {"type": "string", "description": "Risk level assessment"},
        },
        required=("action_type", "description"),
    ),
    write_tool(
        "approvals",
        "approve",
        "Approve a pending approval item.",
        {
            "approval_id": {"type": "string", "description": "Approval UUID"},
            "comment": {"type": "string", "description": "Approval comment"},
        },
        required=("approval_id",),
    ),
    write_tool(
        "approvals",
        "reject",
        "Reject a pending approval item.",
        {
            "approval_id": {"type": "string", "description": "Approval UUID"},
            "reason": {"type": "string", "description": "Rejection reason"},
        },
        required=("approval_id",),
    ),
)
