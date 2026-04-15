"""Task domain handlers."""

from synthorg.meta.mcp.handlers.common import make_handlers_for_tools

TASK_HANDLERS: dict[str, object] = make_handlers_for_tools(
    (
        "synthorg_tasks_list",
        "synthorg_tasks_get",
        "synthorg_tasks_create",
        "synthorg_tasks_update",
        "synthorg_tasks_delete",
        "synthorg_tasks_transition",
        "synthorg_tasks_cancel",
        "synthorg_activities_list",
    )
)
