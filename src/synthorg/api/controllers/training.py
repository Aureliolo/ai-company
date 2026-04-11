"""Training mode API controller.

Provides endpoints for creating, executing, previewing, and
querying training plans for agent onboarding.
"""

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from litestar import Controller, get, post, put
from litestar.status_codes import HTTP_200_OK

from synthorg.api.dto import ApiResponse
from synthorg.api.dto_training import (
    CreateTrainingPlanRequest,
    TrainingPlanResponse,
    TrainingResultResponse,
    UpdateTrainingOverridesRequest,
)
from synthorg.api.errors import (
    ApiValidationError,
    NotFoundError,
    ServiceUnavailableError,
)
from synthorg.api.guards import require_org_mutation, require_read_access
from synthorg.api.path_params import PathName  # noqa: TC001
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.core.agent import AgentIdentity  # noqa: TC001
from synthorg.core.types import NotBlankStr
from synthorg.hr.training.models import (
    ContentType,
    TrainingPlan,
)
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_REQUEST_ERROR,
    API_RESOURCE_NOT_FOUND,
)
from synthorg.observability.events.training import (
    HR_TRAINING_PLAN_CREATED,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = get_logger(__name__)


class _TrainingPlanStore:
    """Async-safe in-memory store for training plans and results.

    This is a placeholder until training plan persistence lands
    (tracked as a follow-up).  It is ``asyncio``-safe within a
    single process; multi-worker deployments will need a real
    persistence backend exposed via ``AppState``.
    """

    def __init__(self) -> None:
        self._plans: dict[str, TrainingPlan] = {}
        # Results are keyed by plan_id so results for different plans
        # on the same agent are never overwritten. A second map tracks
        # the latest plan_id per agent to support the "get latest
        # result by agent" endpoint semantics.
        self._results: dict[str, TrainingResultResponse] = {}
        self._latest_plan_by_agent: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def save_plan(self, plan: TrainingPlan) -> None:
        """Persist a training plan by id."""
        async with self._lock:
            self._plans[str(plan.id)] = plan

    async def get_plan(self, plan_id: str) -> TrainingPlan | None:
        """Fetch a training plan by id."""
        async with self._lock:
            return self._plans.get(plan_id)

    async def latest_pending_plan(self, agent_id: str) -> TrainingPlan | None:
        """Return the most recently created PENDING plan for an agent."""
        from synthorg.hr.training.models import TrainingPlanStatus  # noqa: PLC0415

        async with self._lock:
            pending = [
                plan
                for plan in self._plans.values()
                if str(plan.new_agent_id) == agent_id
                and plan.status == TrainingPlanStatus.PENDING
            ]
        if not pending:
            return None
        return max(pending, key=lambda p: p.created_at)

    async def snapshot_plans(self) -> Mapping[str, TrainingPlan]:
        """Return a read-only snapshot of all plans."""
        async with self._lock:
            return dict(self._plans)

    async def save_result(
        self,
        agent_id: str,
        plan_id: str,
        result: TrainingResultResponse,
    ) -> None:
        """Persist a training result by plan id.

        Also records ``plan_id`` as the latest result for
        ``agent_id`` so the agent-scoped lookup can resolve it.
        """
        async with self._lock:
            self._results[plan_id] = result
            self._latest_plan_by_agent[agent_id] = plan_id

    async def get_result_by_plan(
        self,
        plan_id: str,
    ) -> TrainingResultResponse | None:
        """Fetch a stored training result by plan id."""
        async with self._lock:
            return self._results.get(plan_id)

    async def get_latest_result(
        self,
        agent_id: str,
    ) -> TrainingResultResponse | None:
        """Fetch the latest training result for an agent."""
        async with self._lock:
            plan_id = self._latest_plan_by_agent.get(agent_id)
            if plan_id is None:
                return None
            return self._results.get(plan_id)


# Process-local store singleton. Will be replaced with persistence
# in a follow-up issue (see CodeRabbit #1232 review).
_store = _TrainingPlanStore()


async def _resolve_agent(
    app_state: AppState,
    agent_name: PathName,
) -> AgentIdentity:
    """Resolve agent name to identity, raising NotFoundError."""
    identity = await app_state.agent_registry.get_by_name(agent_name)
    if identity is None:
        logger.warning(
            API_RESOURCE_NOT_FOUND,
            resource="agent",
            name=str(agent_name),
        )
        msg = "Agent not found"
        raise NotFoundError(msg)
    return identity


def _parse_content_types(
    raw: tuple[ContentType, ...] | None,
) -> frozenset[ContentType]:
    """Convert validated content types, defaulting to all when empty."""
    if not raw:
        return frozenset(ContentType)
    return frozenset(raw)


def _parse_custom_caps(
    raw: dict[ContentType, int] | None,
    *,
    defaults: tuple[tuple[ContentType, int], ...],
) -> tuple[tuple[ContentType, int], ...] | None:
    """Merge validated custom caps with defaults for any unspecified types.

    Args:
        raw: Validated caps dict from the request DTO.  Keys are
            ``ContentType`` enums (parsed by Pydantic), values are
            positive integers (validated by DTO ``PositiveInt``).
            May be ``None`` when no override is supplied.
        defaults: The fallback caps for any content type not present
            in ``raw`` -- typically the plan's default volume caps.

    Returns:
        A merged caps tuple covering every known content type, or
        ``None`` when ``raw`` was not provided.
    """
    if not raw:
        return None
    merged: dict[ContentType, int] = dict(defaults)
    merged.update(raw)
    return tuple(merged.items())


def _coerce_override_sources(
    raw: tuple[str, ...],
) -> tuple[NotBlankStr, ...]:
    """Validate override_sources as non-blank identifier strings."""
    coerced: list[NotBlankStr] = []
    for raw_id in raw:
        stripped = raw_id.strip()
        if not stripped:
            msg = "override_sources entries must be non-blank"
            logger.warning(API_REQUEST_ERROR, error=msg)
            raise ApiValidationError(msg)
        coerced.append(NotBlankStr(stripped))
    return tuple(coerced)


class TrainingController(Controller):
    """Training mode API endpoints."""

    path = "/api/v1/agents/{agent_name:str}/training"

    @post(
        "/plan",
        guards=[require_org_mutation()],
        status_code=HTTP_200_OK,
    )
    async def create_plan(
        self,
        app_state: AppState,
        agent_name: PathName,
        data: CreateTrainingPlanRequest,
    ) -> ApiResponse[TrainingPlanResponse]:
        """Create a training plan for the specified agent.

        Args:
            app_state: Litestar application state.
            agent_name: Agent identifier from the URL path.
            data: Request body (content types, caps, overrides, flags).

        Returns:
            ``ApiResponse`` wrapping the created plan response DTO.

        Raises:
            ApiValidationError: If the request contains invalid
                content types, caps, or override sources.
            NotFoundError: If the agent name does not resolve.
        """
        identity = await _resolve_agent(app_state, agent_name)
        enabled_types = _parse_content_types(data.content_types)
        override_sources = _coerce_override_sources(data.override_sources)

        plan_kwargs: dict[str, object] = {
            "new_agent_id": str(identity.id),
            "new_agent_role": str(identity.role),
            "new_agent_level": identity.level,
            "new_agent_department": str(identity.department),
            "override_sources": override_sources,
            "enabled_content_types": enabled_types,
            "skip_training": data.skip_training,
            "require_review": data.require_review,
            "created_at": datetime.now(UTC),
        }

        # Use TrainingPlan's default caps for the merge baseline so
        # omitted content types remain capped at the documented default
        # instead of becoming unlimited.
        default_caps = TrainingPlan.model_fields["volume_caps"].default
        caps = _parse_custom_caps(data.custom_caps, defaults=default_caps)
        if caps is not None:
            plan_kwargs["volume_caps"] = caps

        plan = TrainingPlan(**plan_kwargs)  # type: ignore[arg-type]
        await _store.save_plan(plan)

        logger.info(
            HR_TRAINING_PLAN_CREATED,
            plan_id=str(plan.id),
            agent_name=str(agent_name),
        )

        return ApiResponse(data=_plan_to_response(plan))

    @post(
        "/execute",
        guards=[require_org_mutation()],
        status_code=HTTP_200_OK,
    )
    async def execute_plan(
        self,
        app_state: AppState,
        agent_name: PathName,
    ) -> ApiResponse[TrainingResultResponse]:
        """Execute the latest pending training plan.

        Args:
            app_state: Litestar application state.
            agent_name: Agent identifier from the URL path.

        Raises:
            NotFoundError: If no pending plan exists for the agent.
            ServiceUnavailableError: If the training service is not
                yet wired into ``AppState`` for this deployment.
        """
        identity = await _resolve_agent(app_state, agent_name)
        agent_id = str(identity.id)

        plan = await _store.latest_pending_plan(agent_id)
        if plan is None:
            logger.warning(
                API_RESOURCE_NOT_FOUND,
                resource="training_plan",
                agent_id=agent_id,
            )
            msg = "No pending training plan found"
            raise NotFoundError(msg)

        # TrainingService is not yet exposed on AppState (tracked in
        # a follow-up issue). Return 503 so callers can distinguish
        # "agent exists but service unavailable" from "resource missing".
        msg = "Training execution service is not yet wired for this deployment"
        logger.warning(API_REQUEST_ERROR, error=msg, plan_id=str(plan.id))
        raise ServiceUnavailableError(msg)

    @get(
        "/result",
        guards=[require_read_access],
        status_code=HTTP_200_OK,
    )
    async def get_result(
        self,
        app_state: AppState,
        agent_name: PathName,
    ) -> ApiResponse[TrainingResultResponse]:
        """Get the latest training result for an agent.

        Args:
            app_state: Litestar application state.
            agent_name: Agent identifier from the URL path.

        Raises:
            NotFoundError: If no result is stored for the agent.
        """
        identity = await _resolve_agent(app_state, agent_name)
        agent_id = str(identity.id)

        result = await _store.get_latest_result(agent_id)
        if result is None:
            logger.warning(
                API_RESOURCE_NOT_FOUND,
                resource="training_result",
                agent_id=agent_id,
            )
            msg = "No training result found"
            raise NotFoundError(msg)

        return ApiResponse(data=result)

    @post(
        "/preview",
        guards=[require_read_access],
        status_code=HTTP_200_OK,
    )
    async def preview_plan(
        self,
        app_state: AppState,
        agent_name: PathName,
    ) -> ApiResponse[TrainingResultResponse]:
        """Preview a training plan (dry run).

        Args:
            app_state: Litestar application state.
            agent_name: Agent identifier from the URL path.

        Raises:
            NotFoundError: If no pending plan exists for the agent.
            ServiceUnavailableError: If the training service is not
                yet wired into ``AppState`` for this deployment.
        """
        identity = await _resolve_agent(app_state, agent_name)
        agent_id = str(identity.id)

        plan = await _store.latest_pending_plan(agent_id)
        if plan is None:
            logger.warning(
                API_RESOURCE_NOT_FOUND,
                resource="training_plan",
                agent_id=agent_id,
            )
            msg = "No pending training plan found"
            raise NotFoundError(msg)

        msg = "Training preview service is not yet wired for this deployment"
        logger.warning(API_REQUEST_ERROR, error=msg, plan_id=str(plan.id))
        raise ServiceUnavailableError(msg)

    @put(
        "/plan/{plan_id:str}/overrides",
        guards=[require_org_mutation()],
        status_code=HTTP_200_OK,
    )
    async def update_overrides(
        self,
        app_state: AppState,
        agent_name: PathName,
        plan_id: str,
        data: UpdateTrainingOverridesRequest,
    ) -> ApiResponse[TrainingPlanResponse]:
        """Update training plan overrides.

        Args:
            app_state: Litestar application state.
            agent_name: Agent identifier from the URL path.
            plan_id: Training plan id from the URL path.
            data: Request body with optional override updates.

        Returns:
            ``ApiResponse`` wrapping the updated plan response.

        Raises:
            NotFoundError: If the plan or agent cannot be resolved.
            ApiValidationError: If the request contains invalid caps
                or override source ids.
        """
        identity = await _resolve_agent(app_state, agent_name)

        plan = await _store.get_plan(plan_id)
        if plan is None:
            logger.warning(
                API_RESOURCE_NOT_FOUND,
                resource="training_plan",
                plan_id=plan_id,
            )
            msg = "Training plan not found"
            raise NotFoundError(msg)

        if str(plan.new_agent_id) != str(identity.id):
            logger.warning(
                API_RESOURCE_NOT_FOUND,
                resource="training_plan",
                plan_id=plan_id,
                reason="wrong_owner",
            )
            msg = "Training plan does not belong to this agent"
            raise NotFoundError(msg)

        updates: dict[str, object] = {}
        if data.override_sources is not None:
            updates["override_sources"] = _coerce_override_sources(
                data.override_sources,
            )
        caps = _parse_custom_caps(data.custom_caps, defaults=plan.volume_caps)
        if caps is not None:
            updates["volume_caps"] = caps
        if data.content_types is not None:
            updates["enabled_content_types"] = frozenset(data.content_types)
        if data.skip_training is not None:
            updates["skip_training"] = data.skip_training

        updated = plan.model_copy(update=updates)
        await _store.save_plan(updated)

        return ApiResponse(data=_plan_to_response(updated))


def _plan_to_response(plan: TrainingPlan) -> TrainingPlanResponse:
    """Convert a TrainingPlan to a response DTO."""
    return TrainingPlanResponse(
        id=plan.id,
        new_agent_id=plan.new_agent_id,
        new_agent_role=plan.new_agent_role,
        source_selector_type=plan.source_selector_type,
        enabled_content_types=tuple(
            sorted(ct.value for ct in plan.enabled_content_types),
        ),
        curation_strategy_type=plan.curation_strategy_type,
        volume_caps=tuple((ct.value, cap) for ct, cap in plan.volume_caps),
        override_sources=plan.override_sources,
        skip_training=plan.skip_training,
        require_review=plan.require_review,
        status=plan.status,
        created_at=plan.created_at,
        executed_at=plan.executed_at,
    )
