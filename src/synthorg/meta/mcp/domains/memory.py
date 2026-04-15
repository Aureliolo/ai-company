"""Memory domain MCP tools.

Covers memory admin controller (fine-tuning, checkpoints, embedder).
"""

from typing import TYPE_CHECKING

from synthorg.meta.mcp.tool_builder import admin_tool, read_tool

if TYPE_CHECKING:
    from synthorg.meta.mcp.registry import MCPToolDef

_PAGINATION = {
    "offset": {"type": "integer", "description": "Pagination offset", "default": 0},
    "limit": {"type": "integer", "description": "Page size", "default": 50},
}

MEMORY_TOOLS: tuple[MCPToolDef, ...] = (
    # --- Fine-tuning ---
    admin_tool(
        "memory",
        "start_fine_tune",
        "Start a memory fine-tuning pipeline.",
        {
            "config": {"type": "object", "description": "Fine-tune configuration"},
        },
    ),
    admin_tool(
        "memory",
        "resume_fine_tune",
        "Resume a failed or cancelled fine-tune run.",
        {
            "run_id": {"type": "string", "description": "Run ID to resume"},
        },
        required=("run_id",),
    ),
    read_tool(
        "memory", "get_fine_tune_status", "Get the current fine-tune pipeline status."
    ),
    admin_tool("memory", "cancel_fine_tune", "Cancel an active fine-tune pipeline."),
    admin_tool(
        "memory",
        "run_preflight",
        "Run preflight checks before fine-tuning.",
        {
            "config": {
                "type": "object",
                "description": "Fine-tune configuration to validate",
            },
        },
    ),
    # --- Checkpoints ---
    read_tool("memory", "list_checkpoints", "List fine-tune checkpoints.", _PAGINATION),
    admin_tool(
        "memory",
        "deploy_checkpoint",
        "Deploy a fine-tune checkpoint.",
        {
            "checkpoint_id": {"type": "string", "description": "Checkpoint UUID"},
        },
        required=("checkpoint_id",),
    ),
    admin_tool(
        "memory",
        "rollback_checkpoint",
        "Rollback a deployed checkpoint.",
        {
            "checkpoint_id": {"type": "string", "description": "Checkpoint UUID"},
        },
        required=("checkpoint_id",),
    ),
    admin_tool(
        "memory",
        "delete_checkpoint",
        "Delete a fine-tune checkpoint.",
        {
            "checkpoint_id": {"type": "string", "description": "Checkpoint UUID"},
        },
        required=("checkpoint_id",),
    ),
    # --- Runs ---
    read_tool("memory", "list_runs", "List fine-tune pipeline runs.", _PAGINATION),
    # --- Embedder ---
    read_tool(
        "memory",
        "get_active_embedder",
        "Get active embedder configuration (provider, model, dims).",
    ),
)
