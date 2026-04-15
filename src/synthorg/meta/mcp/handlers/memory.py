"""Memory domain handlers."""

from synthorg.meta.mcp.handlers.common import make_handlers_for_tools

MEMORY_HANDLERS: dict[str, object] = make_handlers_for_tools(
    (
        "synthorg_memory_start_fine_tune",
        "synthorg_memory_resume_fine_tune",
        "synthorg_memory_get_fine_tune_status",
        "synthorg_memory_cancel_fine_tune",
        "synthorg_memory_run_preflight",
        "synthorg_memory_list_checkpoints",
        "synthorg_memory_deploy_checkpoint",
        "synthorg_memory_rollback_checkpoint",
        "synthorg_memory_delete_checkpoint",
        "synthorg_memory_list_runs",
        "synthorg_memory_get_active_embedder",
    )
)
