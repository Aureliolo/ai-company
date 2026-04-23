"""Infrastructure domain MCP handlers.

39 tools spanning health, settings, providers, backup, audit, events,
users, projects, requests, setup, simulations, template packs, and
integration health.  The backing services are spread across many
controllers; ``app_state`` exposes ``backup_service``,
``provider_registry``, ``settings_service``, ``auth_service``, etc.,
but not in the read-friendly facade shape the MCP tools expect.

For now, ``synthorg_health_check`` returns a live aggregation from
``app_state`` and every other handler returns ``not_supported`` with a
stable reason.  Destructive writes (backup/settings/users/projects
delete, backup_restore, template_packs_uninstall) enforce the
guardrail triple so auditing stays uniform when service facades land.
"""

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
    ok,
    require_destructive_guardrails,
)
from synthorg.observability import get_logger, safe_error_description
from synthorg.observability.events.mcp import (
    MCP_HANDLER_GUARDRAIL_VIOLATED,
    MCP_HANDLER_INVOKE_FAILED,
    MCP_HANDLER_INVOKE_SUCCESS,
)

if TYPE_CHECKING:
    from synthorg.core.agent import AgentIdentity

logger = get_logger(__name__)


_WHY_SETTINGS = (
    "settings CRUD goes through settings_service; no MCP-friendly "
    "schema or bulk-read method is exposed yet"
)
_WHY_PROVIDERS = (
    "provider list/health/test lives in providers controller; no "
    "ProviderService facade on app_state"
)
_WHY_BACKUP = (
    "backup operations go through backup_service with a full config "
    "payload; no MCP-native schema"
)
_WHY_AUDIT = "audit trail is served by the audit controller; no facade on app_state"
_WHY_EVENTS = "event log is served by the events controller; no facade on app_state"
_WHY_USERS = "user CRUD goes through auth_service; no MCP-friendly read/write schema"
_WHY_PROJECTS = (
    "project CRUD goes through the projects controller; no facade on app_state"
)
_WHY_REQUESTS = "request CRUD lives in the requests controller; no facade on app_state"
_WHY_SETUP = (
    "setup status + initialization run through the setup controller; "
    "no facade on app_state"
)
_WHY_SIMULATIONS = (
    "simulation CRUD lives in the simulations controller; no facade on app_state"
)
_WHY_TEMPLATE_PACKS = (
    "template pack install/uninstall lives in template_packs "
    "controller; no facade on app_state"
)
_WHY_INTEGRATION_HEALTH = (
    "integration health rolls up status via health_prober_service; no MCP read facade"
)


def _log_failed(tool: str, exc: Exception) -> None:
    logger.warning(
        MCP_HANDLER_INVOKE_FAILED,
        tool_name=tool,
        error_type=type(exc).__name__,
        error=safe_error_description(exc),
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


async def _health_check(
    *,
    app_state: Any,
    arguments: dict[str, Any],  # noqa: ARG001
    actor: Any = None,  # noqa: ARG001
) -> str:
    """Live health-check shim.

    Returns a minimal live snapshot of the services known to be wired
    on ``app_state``.  The individual ``has_*`` probes are cheap and
    don't trigger network calls.
    """
    tool = "synthorg_health_check"
    try:
        data = {
            "task_engine": app_state.has_task_engine,
            "cost_tracker": app_state.has_cost_tracker,
            "approval_store": bool(
                getattr(app_state, "approval_store", None) is not None,
            ),
            "agent_registry": app_state.has_agent_registry,
        }
    except Exception as exc:
        _log_failed(tool, exc)
        return err(exc)
    logger.info(MCP_HANDLER_INVOKE_SUCCESS, tool_name=tool)
    return ok(data=data)


INFRASTRUCTURE_HANDLERS: Mapping[str, ToolHandler] = MappingProxyType(
    {
        "synthorg_health_check": _health_check,
        "synthorg_settings_list": _mk("synthorg_settings_list", _WHY_SETTINGS),
        "synthorg_settings_get": _mk("synthorg_settings_get", _WHY_SETTINGS),
        "synthorg_settings_update": _mk(
            "synthorg_settings_update",
            _WHY_SETTINGS,
        ),
        "synthorg_settings_delete": _mk_destructive(
            "synthorg_settings_delete",
            _WHY_SETTINGS,
        ),
        "synthorg_providers_list": _mk(
            "synthorg_providers_list",
            _WHY_PROVIDERS,
        ),
        "synthorg_providers_get": _mk(
            "synthorg_providers_get",
            _WHY_PROVIDERS,
        ),
        "synthorg_providers_get_health": _mk(
            "synthorg_providers_get_health",
            _WHY_PROVIDERS,
        ),
        "synthorg_providers_test_connection": _mk(
            "synthorg_providers_test_connection",
            _WHY_PROVIDERS,
        ),
        "synthorg_backup_create": _mk("synthorg_backup_create", _WHY_BACKUP),
        "synthorg_backup_list": _mk("synthorg_backup_list", _WHY_BACKUP),
        "synthorg_backup_get": _mk("synthorg_backup_get", _WHY_BACKUP),
        "synthorg_backup_delete": _mk_destructive(
            "synthorg_backup_delete",
            _WHY_BACKUP,
        ),
        "synthorg_backup_restore": _mk_destructive(
            "synthorg_backup_restore",
            _WHY_BACKUP,
        ),
        "synthorg_audit_list": _mk("synthorg_audit_list", _WHY_AUDIT),
        "synthorg_events_list": _mk("synthorg_events_list", _WHY_EVENTS),
        "synthorg_users_list": _mk("synthorg_users_list", _WHY_USERS),
        "synthorg_users_get": _mk("synthorg_users_get", _WHY_USERS),
        "synthorg_users_create": _mk("synthorg_users_create", _WHY_USERS),
        "synthorg_users_update": _mk("synthorg_users_update", _WHY_USERS),
        "synthorg_users_delete": _mk_destructive(
            "synthorg_users_delete",
            _WHY_USERS,
        ),
        "synthorg_projects_list": _mk("synthorg_projects_list", _WHY_PROJECTS),
        "synthorg_projects_get": _mk("synthorg_projects_get", _WHY_PROJECTS),
        "synthorg_projects_create": _mk(
            "synthorg_projects_create",
            _WHY_PROJECTS,
        ),
        "synthorg_projects_update": _mk(
            "synthorg_projects_update",
            _WHY_PROJECTS,
        ),
        "synthorg_projects_delete": _mk_destructive(
            "synthorg_projects_delete",
            _WHY_PROJECTS,
        ),
        "synthorg_requests_list": _mk("synthorg_requests_list", _WHY_REQUESTS),
        "synthorg_requests_get": _mk("synthorg_requests_get", _WHY_REQUESTS),
        "synthorg_requests_create": _mk(
            "synthorg_requests_create",
            _WHY_REQUESTS,
        ),
        "synthorg_setup_get_status": _mk(
            "synthorg_setup_get_status",
            _WHY_SETUP,
        ),
        "synthorg_setup_initialize": _mk(
            "synthorg_setup_initialize",
            _WHY_SETUP,
        ),
        "synthorg_simulations_list": _mk(
            "synthorg_simulations_list",
            _WHY_SIMULATIONS,
        ),
        "synthorg_simulations_get": _mk(
            "synthorg_simulations_get",
            _WHY_SIMULATIONS,
        ),
        "synthorg_simulations_create": _mk(
            "synthorg_simulations_create",
            _WHY_SIMULATIONS,
        ),
        "synthorg_template_packs_list": _mk(
            "synthorg_template_packs_list",
            _WHY_TEMPLATE_PACKS,
        ),
        "synthorg_template_packs_get": _mk(
            "synthorg_template_packs_get",
            _WHY_TEMPLATE_PACKS,
        ),
        "synthorg_template_packs_install": _mk(
            "synthorg_template_packs_install",
            _WHY_TEMPLATE_PACKS,
        ),
        "synthorg_template_packs_uninstall": _mk_destructive(
            "synthorg_template_packs_uninstall",
            _WHY_TEMPLATE_PACKS,
        ),
        "synthorg_integration_health_get_all": _mk(
            "synthorg_integration_health_get_all",
            _WHY_INTEGRATION_HEALTH,
        ),
        "synthorg_integration_health_get": _mk(
            "synthorg_integration_health_get",
            _WHY_INTEGRATION_HEALTH,
        ),
    },
)
