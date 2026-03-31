"""Personality preset controller -- discovery and CRUD endpoints."""

from typing import Any

from litestar import Controller, Response, delete, get, post, put
from litestar.datastructures import State  # noqa: TC002

from synthorg.api.dto import ApiResponse, PaginatedResponse
from synthorg.api.dto_personalities import (
    CreatePresetRequest,
    PresetDetailResponse,
    PresetSource,
    PresetSummaryResponse,
    UpdatePresetRequest,
)
from synthorg.api.guards import require_read_access, require_write_access
from synthorg.api.pagination import (
    PaginationLimit,
    PaginationOffset,
    paginate,
)
from synthorg.api.path_params import PathName  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.templates.preset_service import (
    PersonalityPresetService,
    PresetEntry,
)

logger = get_logger(__name__)


def _to_summary(entry: PresetEntry) -> PresetSummaryResponse:
    """Convert a PresetEntry to a list summary response."""
    return PresetSummaryResponse(
        name=entry.name,
        description=entry.description,
        traits=tuple(str(t) for t in entry.config.get("traits", ())),
        source=PresetSource(entry.source),
    )


def _to_detail(entry: PresetEntry) -> PresetDetailResponse:
    """Convert a PresetEntry to a full detail response."""
    cfg = entry.config
    return PresetDetailResponse(
        name=entry.name,
        source=PresetSource(entry.source),
        description=entry.description,
        traits=tuple(str(t) for t in cfg.get("traits", ())),
        communication_style=str(cfg.get("communication_style", "neutral")),
        risk_tolerance=cfg.get("risk_tolerance", "medium"),
        creativity=cfg.get("creativity", "medium"),
        openness=cfg.get("openness", 0.5),
        conscientiousness=cfg.get("conscientiousness", 0.5),
        extraversion=cfg.get("extraversion", 0.5),
        agreeableness=cfg.get("agreeableness", 0.5),
        stress_response=cfg.get("stress_response", 0.5),
        decision_making=cfg.get("decision_making", "consultative"),
        collaboration=cfg.get("collaboration", "team"),
        verbosity=cfg.get("verbosity", "balanced"),
        conflict_approach=cfg.get("conflict_approach", "collaborate"),
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


def _get_service(state: State) -> PersonalityPresetService:
    """Construct a PersonalityPresetService from app state."""
    repo = state.app_state.persistence.custom_presets
    return PersonalityPresetService(repository=repo)


class PersonalityPresetController(Controller):
    """Discovery and CRUD endpoints for personality presets."""

    path = "/personalities"
    tags = ("personalities",)

    # ── Discovery (Issue #755) ───────────────────────────────

    @get(
        "/presets",
        guards=[require_read_access],
    )
    async def list_presets(
        self,
        state: State,
        offset: PaginationOffset = 0,
        limit: PaginationLimit = 50,
    ) -> PaginatedResponse[PresetSummaryResponse]:
        """List all personality presets (builtin + custom)."""
        service = _get_service(state)
        entries = await service.list_all()
        summaries = tuple(_to_summary(e) for e in entries)
        page, meta = paginate(summaries, offset=offset, limit=limit)
        return PaginatedResponse[PresetSummaryResponse](data=page, pagination=meta)

    @get(
        "/presets/{name:str}",
        guards=[require_read_access],
    )
    async def get_preset(
        self,
        state: State,
        name: PathName,
    ) -> ApiResponse[PresetDetailResponse]:
        """Get full details of a personality preset."""
        service = _get_service(state)
        entry = await service.get(name)
        return ApiResponse[PresetDetailResponse](data=_to_detail(entry))

    @get(
        "/schema",
        guards=[require_read_access],
    )
    async def get_schema(self) -> ApiResponse[dict[str, Any]]:
        """Return the PersonalityConfig JSON schema."""
        schema = PersonalityPresetService.get_schema()
        return ApiResponse[dict[str, Any]](data=schema)

    # ── CRUD (Issue #756) ────────────────────────────────────

    @post(
        "/presets",
        guards=[require_write_access],
        status_code=201,
    )
    async def create_preset(
        self,
        state: State,
        data: CreatePresetRequest,
    ) -> Response[ApiResponse[PresetDetailResponse]]:
        """Create a custom personality preset."""
        service = _get_service(state)
        entry = await service.create(data.name, data.to_config_dict())
        return Response(
            content=ApiResponse[PresetDetailResponse](data=_to_detail(entry)),
            status_code=201,
        )

    @put(
        "/presets/{name:str}",
        guards=[require_write_access],
    )
    async def update_preset(
        self,
        state: State,
        name: PathName,
        data: UpdatePresetRequest,
    ) -> ApiResponse[PresetDetailResponse]:
        """Update an existing custom personality preset."""
        service = _get_service(state)
        entry = await service.update(name, data.to_config_dict())
        return ApiResponse[PresetDetailResponse](data=_to_detail(entry))

    @delete(
        "/presets/{name:str}",
        guards=[require_write_access],
        status_code=200,
    )
    async def delete_preset(
        self,
        state: State,
        name: PathName,
    ) -> ApiResponse[None]:
        """Delete a custom personality preset."""
        service = _get_service(state)
        await service.delete(name)
        return ApiResponse[None](data=None)
