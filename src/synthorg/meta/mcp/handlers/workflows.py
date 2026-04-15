"""Workflow domain handlers."""

from synthorg.meta.mcp.handlers.common import make_handlers_for_tools

WORKFLOW_HANDLERS: dict[str, object] = make_handlers_for_tools(
    (
        "synthorg_workflows_list",
        "synthorg_workflows_get",
        "synthorg_workflows_create",
        "synthorg_workflows_update",
        "synthorg_workflows_delete",
        "synthorg_workflows_validate",
        "synthorg_subworkflows_list",
        "synthorg_subworkflows_get",
        "synthorg_subworkflows_create",
        "synthorg_subworkflows_delete",
        "synthorg_workflow_executions_list",
        "synthorg_workflow_executions_get",
        "synthorg_workflow_executions_start",
        "synthorg_workflow_executions_cancel",
        "synthorg_workflow_versions_list",
        "synthorg_workflow_versions_get",
    )
)
