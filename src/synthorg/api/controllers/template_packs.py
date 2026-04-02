"""Template packs controller -- listing and live application."""

import json
from typing import TYPE_CHECKING, Any, Literal

from litestar import Controller, get, post
from litestar.datastructures import State  # noqa: TC002
from litestar.status_codes import HTTP_201_CREATED
from pydantic import BaseModel, ConfigDict, Field

from synthorg.api.controllers.setup_agents import (
    departments_to_json,
    expand_template_agents,
)
from synthorg.api.dto import ApiResponse
from synthorg.api.errors import NotFoundError
from synthorg.api.guards import require_ceo_or_manager, require_read_access
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.template import (
    TEMPLATE_PACK_APPLY_ERROR,
    TEMPLATE_PACK_APPLY_START,
    TEMPLATE_PACK_APPLY_SUCCESS,
    TEMPLATE_PACK_LIST,
)
from synthorg.settings.errors import SettingNotFoundError
from synthorg.templates.errors import TemplateNotFoundError
from synthorg.templates.pack_loader import PackInfo, list_packs, load_pack

if TYPE_CHECKING:
    from collections.abc import Sequence

    from synthorg.templates.schema import TemplateDepartmentConfig

logger = get_logger(__name__)


# ---- DTOs ----------------------------------------------------------------


class PackInfoResponse(BaseModel):
    """Pack summary for the listing endpoint."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    name: NotBlankStr
    display_name: str
    description: str
    source: Literal["builtin", "user"]
    tags: tuple[str, ...]
    agent_count: int = Field(ge=0)
    department_count: int = Field(ge=0)


class ApplyTemplatePackRequest(BaseModel):
    """Request body for applying a template pack."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    pack_name: NotBlankStr = Field(description="Pack to apply")
    variables: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional variable overrides",
    )


class ApplyTemplatePackResponse(BaseModel):
    """Response after applying a template pack."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    pack_name: str
    agents_added: int = Field(ge=0)
    departments_added: int = Field(ge=0)


# ---- Helpers --------------------------------------------------------------


def _pack_info_to_response(info: PackInfo) -> PackInfoResponse:
    """Convert a :class:`PackInfo` to a response DTO."""
    return PackInfoResponse(
        name=info.name,
        display_name=info.display_name,
        description=info.description,
        source=info.source,
        tags=info.tags,
        agent_count=info.agent_count,
        department_count=info.department_count,
    )


async def _read_setting_list(
    app_state: AppState,
    key: str,
) -> list[dict[str, Any]]:
    """Read a JSON list setting from the company namespace."""
    try:
        entry = await app_state.settings_service.get("company", key)
        return json.loads(entry.value) if entry.value else []
    except SettingNotFoundError:
        return []


def _deduplicate_departments(
    pack_name: str,
    pack_depts: Sequence[TemplateDepartmentConfig],
    current_depts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return pack departments that don't conflict with existing ones."""
    existing_names = {str(d.get("name", "")).lower() for d in current_depts}
    if not pack_depts:
        return []
    raw: list[dict[str, Any]] = json.loads(
        departments_to_json(pack_depts),
    )
    new_depts = [d for d in raw if str(d.get("name", "")).lower() not in existing_names]
    if len(new_depts) < len(raw):
        logger.warning(
            TEMPLATE_PACK_APPLY_ERROR,
            pack_name=pack_name,
            action="departments_skipped",
            skipped=len(raw) - len(new_depts),
        )
    return new_depts


async def _persist_merged_config(
    app_state: AppState,
    agents: list[dict[str, Any]],
    departments: list[dict[str, Any]],
) -> None:
    """Write merged agents and departments to settings."""
    settings_svc = app_state.settings_service
    await settings_svc.set(
        "company",
        "agents",
        json.dumps(agents),
    )
    await settings_svc.set(
        "company",
        "departments",
        json.dumps(departments),
    )


# ---- Controller -----------------------------------------------------------


class TemplatePackController(Controller):
    """Template pack listing and live application."""

    path = "/template-packs"
    tags = ("template-packs",)

    @get(guards=[require_read_access])
    async def list_template_packs(
        self,
    ) -> ApiResponse[tuple[PackInfoResponse, ...]]:
        """List all available template packs.

        Returns:
            Pack info envelope.
        """
        packs = list_packs()
        logger.info(TEMPLATE_PACK_LIST, count=len(packs))
        return ApiResponse(
            data=tuple(_pack_info_to_response(p) for p in packs),
        )

    @post(
        "/apply",
        status_code=HTTP_201_CREATED,
        guards=[require_ceo_or_manager],
    )
    async def apply_template_pack(
        self,
        data: ApplyTemplatePackRequest,
        state: State,
    ) -> ApiResponse[ApplyTemplatePackResponse]:
        """Apply a template pack to the running organization.

        Args:
            data: Pack name and optional variables.
            state: Application state.

        Returns:
            Summary of agents and departments added.
        """
        app_state: AppState = state.app_state
        logger.info(
            TEMPLATE_PACK_APPLY_START,
            pack_name=data.pack_name,
        )

        try:
            loaded = load_pack(data.pack_name)
        except TemplateNotFoundError as exc:
            logger.warning(
                TEMPLATE_PACK_APPLY_ERROR,
                pack_name=data.pack_name,
                error=str(exc),
            )
            msg = f"Template pack {data.pack_name!r} not found"
            raise NotFoundError(msg) from exc

        pack_agents = expand_template_agents(loaded.template)
        current_agents = await _read_setting_list(app_state, "agents")
        current_depts = await _read_setting_list(app_state, "departments")

        new_depts = _deduplicate_departments(
            data.pack_name,
            loaded.template.departments,
            current_depts,
        )

        await _persist_merged_config(
            app_state,
            current_agents + pack_agents,
            current_depts + new_depts,
        )

        logger.info(
            TEMPLATE_PACK_APPLY_SUCCESS,
            pack_name=data.pack_name,
            agents_added=len(pack_agents),
            departments_added=len(new_depts),
        )
        return ApiResponse(
            data=ApplyTemplatePackResponse(
                pack_name=data.pack_name,
                agents_added=len(pack_agents),
                departments_added=len(new_depts),
            ),
        )
