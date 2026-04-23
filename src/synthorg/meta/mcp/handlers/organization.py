"""Organization domain MCP handlers.

19 tools across company, departments, teams, and role-version history.
``app_state.org_mutation_service`` covers most mutations but expects
full entity payloads; reads go through the api controllers without a
service facade.  Every handler returns ``not_supported`` until an
OrgReadService + OrgWriteService pair is added to ``app_state``.

Destructive deletes (``departments.delete``, ``teams.delete``) enforce
the guardrail triple at the handler boundary even when routed to
``not_supported`` so the audit surface is uniform once services come
online.
"""

from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from synthorg.meta.mcp.errors import GuardrailViolationError
from synthorg.meta.mcp.handlers.common import (
    err,
    not_supported,
    require_destructive_guardrails,
)
from synthorg.observability import get_logger
from synthorg.observability.events.mcp import MCP_HANDLER_GUARDRAIL_VIOLATED

if TYPE_CHECKING:
    from collections.abc import Mapping

    from synthorg.core.agent import AgentIdentity
    from synthorg.meta.mcp.invoker import ToolHandler

logger = get_logger(__name__)


_WHY_COMPANY = (
    "company config read/write goes through company controller + "
    "org_mutation_service; no consolidated CompanyService facade on "
    "app_state"
)
_WHY_DEPARTMENTS = (
    "department CRUD goes through the departments controller; no "
    "DepartmentService facade on app_state"
)
_WHY_TEAMS = (
    "team CRUD goes through the teams controller; no TeamService facade on app_state"
)
_WHY_ROLE_VERSIONS = (
    "role-version history reads go through the role_versions "
    "controller; no service facade on app_state"
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
    actor: Any,
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


ORGANIZATION_HANDLERS: Mapping[str, ToolHandler] = MappingProxyType(
    {
        "synthorg_company_get": _mk("synthorg_company_get", _WHY_COMPANY),
        "synthorg_company_update": _mk("synthorg_company_update", _WHY_COMPANY),
        "synthorg_company_list_departments": _mk(
            "synthorg_company_list_departments",
            _WHY_COMPANY,
        ),
        "synthorg_company_reorder_departments": _mk(
            "synthorg_company_reorder_departments",
            _WHY_COMPANY,
        ),
        "synthorg_company_versions_list": _mk(
            "synthorg_company_versions_list",
            _WHY_COMPANY,
        ),
        "synthorg_company_versions_get": _mk(
            "synthorg_company_versions_get",
            _WHY_COMPANY,
        ),
        "synthorg_departments_list": _mk(
            "synthorg_departments_list",
            _WHY_DEPARTMENTS,
        ),
        "synthorg_departments_get": _mk(
            "synthorg_departments_get",
            _WHY_DEPARTMENTS,
        ),
        "synthorg_departments_create": _mk(
            "synthorg_departments_create",
            _WHY_DEPARTMENTS,
        ),
        "synthorg_departments_update": _mk(
            "synthorg_departments_update",
            _WHY_DEPARTMENTS,
        ),
        "synthorg_departments_delete": _mk_destructive(
            "synthorg_departments_delete",
            _WHY_DEPARTMENTS,
        ),
        "synthorg_departments_get_health": _mk(
            "synthorg_departments_get_health",
            _WHY_DEPARTMENTS,
        ),
        "synthorg_teams_list": _mk("synthorg_teams_list", _WHY_TEAMS),
        "synthorg_teams_get": _mk("synthorg_teams_get", _WHY_TEAMS),
        "synthorg_teams_create": _mk("synthorg_teams_create", _WHY_TEAMS),
        "synthorg_teams_update": _mk("synthorg_teams_update", _WHY_TEAMS),
        "synthorg_teams_delete": _mk_destructive(
            "synthorg_teams_delete",
            _WHY_TEAMS,
        ),
        "synthorg_role_versions_list": _mk(
            "synthorg_role_versions_list",
            _WHY_ROLE_VERSIONS,
        ),
        "synthorg_role_versions_get": _mk(
            "synthorg_role_versions_get",
            _WHY_ROLE_VERSIONS,
        ),
    },
)
