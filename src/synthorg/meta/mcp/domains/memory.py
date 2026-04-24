"""Memory domain MCP tools.

Covers memory admin controller (fine-tuning, checkpoints, embedder).
"""

from typing import TYPE_CHECKING

from synthorg.meta.mcp.tool_builder import (
    DESTRUCTIVE_GUARDRAIL_PROPERTIES,
    PAGINATION_PROPERTIES,
    admin_tool,
    read_tool,
)

if TYPE_CHECKING:
    from synthorg.meta.mcp.registry import MCPToolDef

# Explicit FineTunePlan fields -- keeps the wire-level contract in sync
# with the Pydantic model in ``synthorg.memory.fine_tune_plan.FineTunePlan``
# so MCP clients receive schema-level validation errors instead of opaque
# "config" object rejections from the handler.
_FINE_TUNE_PLAN_PROPERTIES: dict[str, object] = {
    "source_dir": {
        "type": "string",
        "description": "Directory containing org documents for training",
        "minLength": 1,
    },
    "base_model": {
        "type": ["string", "null"],
        "description": "Base model to fine-tune (null = active model)",
    },
    "output_dir": {
        "type": ["string", "null"],
        "description": "Checkpoint output directory (null = default)",
    },
    "resume_run_id": {
        "type": ["string", "null"],
        "description": "Resume a previous failed/cancelled run",
    },
    "epochs": {
        "type": ["integer", "null"],
        "description": "Override training epochs",
        "minimum": 1,
    },
    "learning_rate": {
        "type": ["number", "null"],
        "description": "Override learning rate",
        "exclusiveMinimum": 0.0,
    },
    "temperature": {
        "type": ["number", "null"],
        "description": "Override InfoNCE temperature",
        "exclusiveMinimum": 0.0,
    },
    "top_k": {
        "type": ["integer", "null"],
        "description": "Override hard negative count per query",
        "minimum": 1,
    },
    "batch_size": {
        "type": ["integer", "null"],
        "description": "Override training batch size",
        "minimum": 1,
    },
    "validation_split": {
        "type": ["number", "null"],
        "description": "Fraction held out for evaluation (0 < v < 1)",
        "exclusiveMinimum": 0.0,
        "exclusiveMaximum": 1.0,
    },
    "execution": {
        "type": ["object", "null"],
        "description": "Optional runner-backend execution config",
    },
}

MEMORY_TOOLS: tuple[MCPToolDef, ...] = (
    # --- Fine-tuning ---
    admin_tool(
        "memory",
        "start_fine_tune",
        "Start a memory fine-tuning pipeline.",
        _FINE_TUNE_PLAN_PROPERTIES,
        required=("source_dir",),
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
    admin_tool(
        "memory",
        "cancel_fine_tune",
        "Cancel an active fine-tune pipeline (destructive; requires confirm).",
        {**DESTRUCTIVE_GUARDRAIL_PROPERTIES},
        required=("reason", "confirm"),
    ),
    admin_tool(
        "memory",
        "run_preflight",
        "Run preflight checks before fine-tuning.",
        _FINE_TUNE_PLAN_PROPERTIES,
        required=("source_dir",),
    ),
    # --- Checkpoints ---
    read_tool(
        "memory",
        "list_checkpoints",
        "List fine-tune checkpoints.",
        PAGINATION_PROPERTIES,
    ),
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
        "Rollback a deployed checkpoint (destructive; requires confirm).",
        {
            "checkpoint_id": {"type": "string", "description": "Checkpoint UUID"},
            **DESTRUCTIVE_GUARDRAIL_PROPERTIES,
        },
        required=("checkpoint_id", "reason", "confirm"),
    ),
    admin_tool(
        "memory",
        "delete_checkpoint",
        "Delete a fine-tune checkpoint (destructive; requires confirm).",
        {
            "checkpoint_id": {"type": "string", "description": "Checkpoint UUID"},
            **DESTRUCTIVE_GUARDRAIL_PROPERTIES,
        },
        required=("checkpoint_id", "reason", "confirm"),
    ),
    # --- Runs ---
    read_tool(
        "memory", "list_runs", "List fine-tune pipeline runs.", PAGINATION_PROPERTIES
    ),
    # --- Embedder ---
    read_tool(
        "memory",
        "get_active_embedder",
        "Get active embedder configuration (provider, model, dims).",
    ),
)
