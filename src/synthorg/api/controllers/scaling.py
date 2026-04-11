"""Scaling controller -- REST endpoints for dynamic company scaling.

Exposes scaling strategies, decisions, signals, and manual
evaluation triggers.
"""

from litestar import Controller, State, get, post
from pydantic import BaseModel, ConfigDict, Field

from synthorg.api.dto import ApiResponse, PaginatedResponse, PaginationMeta
from synthorg.api.guards import require_read_access, require_write_access
from synthorg.api.pagination import PaginationLimit, PaginationOffset, paginate
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.core.types import NotBlankStr
from synthorg.hr.scaling.models import ScalingDecision  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.hr import (
    HR_SCALING_CYCLE_STARTED,
)

logger = get_logger(__name__)


# -- Response DTOs -----------------------------------------------------------


class ScalingStrategyResponse(BaseModel):
    """Strategy summary for API responses."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    name: str = Field(description="Strategy identifier")
    enabled: bool = Field(description="Whether this strategy is active")
    priority: int = Field(ge=0, description="Priority rank")


class ScalingDecisionResponse(BaseModel):
    """Decision summary for API responses."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    id: str = Field(description="Decision identifier")
    action_type: str = Field(description="Action type")
    source_strategy: str = Field(description="Strategy that proposed this")
    target_agent_id: str | None = Field(
        default=None,
        description="Agent targeted for pruning",
    )
    target_role: str | None = Field(
        default=None,
        description="Role to hire for",
    )
    rationale: str = Field(description="Decision rationale")
    confidence: float = Field(description="Strategy confidence")
    created_at: str = Field(description="ISO timestamp")


class ScalingSignalResponse(BaseModel):
    """Signal value for API responses."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    name: str = Field(description="Signal name")
    value: float = Field(description="Current value")
    source: str = Field(description="Signal source")


def _decision_to_response(d: ScalingDecision) -> ScalingDecisionResponse:
    """Convert a domain decision to a response DTO."""
    return ScalingDecisionResponse(
        id=str(d.id),
        action_type=d.action_type.value,
        source_strategy=d.source_strategy.value,
        target_agent_id=str(d.target_agent_id) if d.target_agent_id else None,
        target_role=str(d.target_role) if d.target_role else None,
        rationale=str(d.rationale),
        confidence=d.confidence,
        created_at=d.created_at.isoformat(),
    )


# -- Controller --------------------------------------------------------------


class ScalingController(Controller):
    """Dynamic company scaling endpoints."""

    path = "/scaling"
    tags = ("scaling",)

    @get("/strategies", guards=[require_read_access])
    async def list_strategies(
        self,
        state: State,
    ) -> ApiResponse[tuple[ScalingStrategyResponse, ...]]:
        """List all scaling strategies with their current status.

        Args:
            state: Application state.

        Returns:
            Strategy list with enabled/priority info.
        """
        app_state: AppState = state.app_state
        scaling = app_state.scaling_service
        if scaling is None:
            return ApiResponse(data=())

        strategies = tuple(
            ScalingStrategyResponse(
                name=str(s.name),
                enabled=True,
                priority=idx,
            )
            for idx, s in enumerate(scaling._strategies)  # noqa: SLF001
        )
        return ApiResponse(data=strategies)

    @get("/decisions", guards=[require_read_access])
    async def list_decisions(
        self,
        state: State,
        offset: PaginationOffset = 0,
        limit: PaginationLimit = 50,
    ) -> PaginatedResponse[ScalingDecisionResponse]:
        """List recent scaling decisions.

        Args:
            state: Application state.
            offset: Pagination offset.
            limit: Page size.

        Returns:
            Paginated list of recent decisions.
        """
        app_state: AppState = state.app_state
        scaling = app_state.scaling_service
        if scaling is None:
            return PaginatedResponse(
                data=(),
                pagination=PaginationMeta(
                    total=0,
                    offset=offset,
                    limit=limit,
                ),
            )

        decisions = scaling.get_recent_decisions()
        responses = tuple(_decision_to_response(d) for d in decisions)
        page, meta = paginate(responses, offset=offset, limit=limit)
        return PaginatedResponse(data=page, pagination=meta)

    @get("/signals", guards=[require_read_access])
    async def list_signals(
        self,
        state: State,
    ) -> ApiResponse[tuple[ScalingSignalResponse, ...]]:
        """Get current signal values for dashboard display.

        Args:
            state: Application state.

        Returns:
            Current signal values from all sources.
        """
        app_state: AppState = state.app_state
        scaling = app_state.scaling_service
        if scaling is None:
            return ApiResponse(data=())

        # Collect signals from the most recent decisions.
        signals: list[ScalingSignalResponse] = []
        seen: set[str] = set()
        for decision in reversed(scaling.get_recent_decisions()):
            for signal in decision.signals:
                if signal.name not in seen:
                    seen.add(str(signal.name))
                    signals.append(
                        ScalingSignalResponse(
                            name=str(signal.name),
                            value=signal.value,
                            source=str(signal.source),
                        ),
                    )
        return ApiResponse(data=tuple(signals))

    @post("/evaluate", guards=[require_write_access])
    async def trigger_evaluation(
        self,
        state: State,
    ) -> ApiResponse[tuple[ScalingDecisionResponse, ...]]:
        """Manually trigger a scaling evaluation cycle.

        Args:
            state: Application state.

        Returns:
            Decisions produced by the evaluation.
        """
        app_state: AppState = state.app_state
        scaling = app_state.scaling_service
        if scaling is None:
            return ApiResponse(
                data=(),
                error="Scaling service not configured",
            )

        logger.info(HR_SCALING_CYCLE_STARTED, trigger="manual")

        # Get active agents from registry.
        registry = app_state.agent_registry
        agents = await registry.list_active()
        agent_ids = tuple(NotBlankStr(str(a.id)) for a in agents)

        decisions = await scaling.evaluate(agent_ids=agent_ids)
        responses = tuple(_decision_to_response(d) for d in decisions)
        return ApiResponse(data=responses)
