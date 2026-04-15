"""Organization domain handlers."""

from synthorg.meta.mcp.handlers.common import make_handlers_for_tools

ORGANIZATION_HANDLERS: dict[str, object] = make_handlers_for_tools(
    (
        "synthorg_company_get",
        "synthorg_company_update",
        "synthorg_company_list_departments",
        "synthorg_company_reorder_departments",
        "synthorg_company_versions_list",
        "synthorg_company_versions_get",
        "synthorg_departments_list",
        "synthorg_departments_get",
        "synthorg_departments_create",
        "synthorg_departments_update",
        "synthorg_departments_delete",
        "synthorg_departments_get_health",
        "synthorg_teams_list",
        "synthorg_teams_get",
        "synthorg_teams_create",
        "synthorg_teams_update",
        "synthorg_teams_delete",
        "synthorg_role_versions_list",
        "synthorg_role_versions_get",
    )
)
