"""Integrations domain handlers."""

from synthorg.meta.mcp.handlers.common import make_handlers_for_tools

INTEGRATION_HANDLERS: dict[str, object] = make_handlers_for_tools(
    (
        "synthorg_mcp_catalog_list",
        "synthorg_mcp_catalog_search",
        "synthorg_mcp_catalog_get",
        "synthorg_mcp_catalog_install",
        "synthorg_mcp_catalog_uninstall",
        "synthorg_oauth_list_providers",
        "synthorg_oauth_configure_provider",
        "synthorg_oauth_remove_provider",
        "synthorg_clients_list",
        "synthorg_clients_get",
        "synthorg_clients_create",
        "synthorg_clients_deactivate",
        "synthorg_clients_get_satisfaction",
        "synthorg_artifacts_list",
        "synthorg_artifacts_get",
        "synthorg_artifacts_create",
        "synthorg_artifacts_delete",
        "synthorg_ontology_list_entities",
        "synthorg_ontology_get_entity",
        "synthorg_ontology_get_relationships",
        "synthorg_ontology_search",
    )
)
