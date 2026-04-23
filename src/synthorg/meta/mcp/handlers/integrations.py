"""Integrations domain MCP handlers.

21 tools spanning the MCP server catalog, OAuth providers, external
clients, artifacts, and the ontology.  Service coverage is uneven and
most paths don't have a clean public-facing method on ``app_state``
for the MCP shim to call; all handlers return a ``not_supported``
envelope with a stable reason string, keeping the full tool surface
visible to ops.

Destructive ops enforce the standard guardrail triple even when they
currently route to ``not_supported``, so auditing behaviour stays
uniform once services come online.
"""

import copy
from collections.abc import Mapping  # noqa: TC003 -- PEP 649 annotation
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from synthorg.meta.mcp.errors import GuardrailViolationError
from synthorg.meta.mcp.handler_protocol import (
    ToolHandler,  # noqa: TC001 -- PEP 649 annotation
)
from synthorg.meta.mcp.handlers.common import (
    err,
    not_supported,
    require_destructive_guardrails,
)
from synthorg.observability import get_logger
from synthorg.observability.events.mcp import MCP_HANDLER_GUARDRAIL_VIOLATED

if TYPE_CHECKING:
    from synthorg.core.agent import AgentIdentity

logger = get_logger(__name__)


_WHY_CATALOG = (
    "MCP catalog browse/install runs through the catalog service but "
    "no list-all / install-by-id method is publicly exposed; use the "
    "/mcp_catalog REST endpoints"
)
_WHY_OAUTH = (
    "OAuth provider management is controller-local; OAuthTokenManager "
    "exposes only token ops, not provider CRUD"
)
_WHY_CLIENTS = (
    "external-client CRUD lives in the clients controller; no "
    "ClientService facade on app_state"
)
_WHY_ARTIFACTS = (
    "artifact CRUD lives in the artifacts controller; no "
    "ArtifactService facade on app_state"
)
_WHY_ONTOLOGY = (
    "ontology reads go through the ontology controller; no list/get "
    "facade is wired to app_state for MCP consumption"
)


def _log_guardrail(tool: str, exc: GuardrailViolationError) -> None:
    logger.warning(
        MCP_HANDLER_GUARDRAIL_VIOLATED,
        tool_name=tool,
        violation=exc.violation,
    )


async def _enforce_destructive(
    tool: str,
    arguments: dict[str, Any],
    actor: AgentIdentity | None,
    why: str,
) -> str:
    try:
        require_destructive_guardrails(arguments, actor)
    except GuardrailViolationError as exc:
        _log_guardrail(tool, exc)
        return err(exc)
    return not_supported(tool, why)


def _mk(tool: str, why: str) -> ToolHandler:
    async def handler(
        *,
        app_state: Any,  # noqa: ARG001
        arguments: dict[str, Any],  # noqa: ARG001
        actor: AgentIdentity | None = None,  # noqa: ARG001
    ) -> str:
        return not_supported(tool, why)

    return handler


def _mk_destructive(tool: str, why: str) -> ToolHandler:
    async def handler(
        *,
        app_state: Any,  # noqa: ARG001
        arguments: dict[str, Any],
        actor: AgentIdentity | None = None,
    ) -> str:
        return await _enforce_destructive(tool, arguments, actor, why)

    return handler


INTEGRATION_HANDLERS: Mapping[str, ToolHandler] = MappingProxyType(
    copy.deepcopy(
        {
            "synthorg_mcp_catalog_list": _mk(
                "synthorg_mcp_catalog_list",
                _WHY_CATALOG,
            ),
            "synthorg_mcp_catalog_search": _mk(
                "synthorg_mcp_catalog_search",
                _WHY_CATALOG,
            ),
            "synthorg_mcp_catalog_get": _mk(
                "synthorg_mcp_catalog_get",
                _WHY_CATALOG,
            ),
            "synthorg_mcp_catalog_install": _mk(
                "synthorg_mcp_catalog_install",
                _WHY_CATALOG,
            ),
            "synthorg_mcp_catalog_uninstall": _mk_destructive(
                "synthorg_mcp_catalog_uninstall",
                _WHY_CATALOG,
            ),
            "synthorg_oauth_list_providers": _mk(
                "synthorg_oauth_list_providers",
                _WHY_OAUTH,
            ),
            "synthorg_oauth_configure_provider": _mk(
                "synthorg_oauth_configure_provider",
                _WHY_OAUTH,
            ),
            "synthorg_oauth_remove_provider": _mk_destructive(
                "synthorg_oauth_remove_provider",
                _WHY_OAUTH,
            ),
            "synthorg_clients_list": _mk("synthorg_clients_list", _WHY_CLIENTS),
            "synthorg_clients_get": _mk("synthorg_clients_get", _WHY_CLIENTS),
            "synthorg_clients_create": _mk("synthorg_clients_create", _WHY_CLIENTS),
            "synthorg_clients_deactivate": _mk_destructive(
                "synthorg_clients_deactivate",
                _WHY_CLIENTS,
            ),
            "synthorg_clients_get_satisfaction": _mk(
                "synthorg_clients_get_satisfaction",
                _WHY_CLIENTS,
            ),
            "synthorg_artifacts_list": _mk(
                "synthorg_artifacts_list",
                _WHY_ARTIFACTS,
            ),
            "synthorg_artifacts_get": _mk("synthorg_artifacts_get", _WHY_ARTIFACTS),
            "synthorg_artifacts_create": _mk(
                "synthorg_artifacts_create",
                _WHY_ARTIFACTS,
            ),
            "synthorg_artifacts_delete": _mk_destructive(
                "synthorg_artifacts_delete",
                _WHY_ARTIFACTS,
            ),
            "synthorg_ontology_list_entities": _mk(
                "synthorg_ontology_list_entities",
                _WHY_ONTOLOGY,
            ),
            "synthorg_ontology_get_entity": _mk(
                "synthorg_ontology_get_entity",
                _WHY_ONTOLOGY,
            ),
            "synthorg_ontology_get_relationships": _mk(
                "synthorg_ontology_get_relationships",
                _WHY_ONTOLOGY,
            ),
            "synthorg_ontology_search": _mk(
                "synthorg_ontology_search",
                _WHY_ONTOLOGY,
            ),
        },
    ),
)
