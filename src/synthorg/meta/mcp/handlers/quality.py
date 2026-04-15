"""Quality domain handlers."""

from synthorg.meta.mcp.handlers.common import make_handlers_for_tools

QUALITY_HANDLERS: dict[str, object] = make_handlers_for_tools(
    (
        "synthorg_quality_get_summary",
        "synthorg_quality_get_agent_quality",
        "synthorg_quality_list_scores",
        "synthorg_reviews_list",
        "synthorg_reviews_get",
        "synthorg_reviews_create",
        "synthorg_reviews_update",
        "synthorg_evaluation_versions_list",
        "synthorg_evaluation_versions_get",
    )
)
