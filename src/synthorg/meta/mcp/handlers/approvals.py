"""Approval domain handlers."""

from synthorg.meta.mcp.handlers.common import make_handlers_for_tools

APPROVAL_HANDLERS: dict[str, object] = make_handlers_for_tools(
    (
        "synthorg_approvals_list",
        "synthorg_approvals_get",
        "synthorg_approvals_create",
        "synthorg_approvals_approve",
        "synthorg_approvals_reject",
    )
)
