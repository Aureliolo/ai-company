"""Training mode API controller.

Provides endpoints for creating, executing, previewing, and
querying training plans for agent onboarding.
"""

from datetime import UTC, datetime

from litestar import Controller, get, post, put
from litestar.status_codes import HTTP_200_OK

from synthorg.api.dto import ApiResponse
from synthorg.api.dto_training import (
    CreateTrainingPlanRequest,
    TrainingPlanResponse,
    TrainingResultResponse,
    UpdateTrainingOverridesRequest,
)
from synthorg.api.errors import ApiValidationError, NotFoundError
from synthorg.api.guards import require_org_mutation, require_read_access
from synthorg.api.path_params import PathName  # noqa: TC001
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.core.agent import AgentIdentity  # noqa: TC001
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

logger = get_logger(__name__)

# In-memory training plan/result stores (will be replaced with
# persistence in a future issue).
_training_plans: dict[str, TrainingPlan] = {}
_training_results: dict[str, TrainingResultResponse] = {}


async def _resolve_agent(
    app_state: AppState,
    agent_name: PathName,
) -> AgentIdentity:
    """Resolve agent name to identity, raising NotFoundError."""
    identity = await app_state.agent_registry.get_by_name(agent_name)
    if identity is None:
        msg = "Agent not found"
        logger.warning(
            API_RESOURCE_NOT_FOUND,
            resource="agent",
            name=str(agent_name),
        )
        raise NotFoundError(msg)
    return identity


def _parse_content_types(
    raw: tuple[str, ...] | None,
) -> frozenset[ContentType]:
    """Parse content type strings, raising ApiValidationError."""
    if not raw:
        return frozenset(ContentType)
    try:
        return frozenset(ContentType(ct) for ct in raw)
    except ValueError as exc:
        msg = f"Invalid content type: {exc}"
        logger.warning(API_REQUEST_ERROR, error=msg)
        raise ApiValidationError(msg) from exc


def _parse_custom_caps(
    raw: dict[str, int] | None,
) -> tuple[tuple[ContentType, int], ...] | None:
    """Parse custom caps dict, validating keys and values."""
    if not raw:
        return None
    try:
        caps = tuple((ContentType(k), v) for k, v in raw.items())
    except ValueError as exc:
        msg = f"Invalid content type in caps: {exc}"
        logger.warning(API_REQUEST_ERROR, error=msg)
        raise ApiValidationError(msg) from exc

    for ct, cap in caps:
        if cap <= 0:
            msg = f"Cap for {ct.value} must be positive, got {cap}"
            raise ApiValidationError(msg)
    return caps


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
        """Create a training plan for an agent."""
        identity = await _resolve_agent(app_state, agent_name)
        enabled_types = _parse_content_types(data.content_types)

        plan_kwargs: dict[str, object] = {
            "new_agent_id": str(identity.id),
            "new_agent_role": str(identity.role),
            "new_agent_level": identity.level,
            "override_sources": data.override_sources,
            "enabled_content_types": enabled_types,
            "skip_training": data.skip_training,
            "require_review": data.require_review,
            "created_at": datetime.now(UTC),
        }
        caps = _parse_custom_caps(data.custom_caps)
        if caps is not None:
            plan_kwargs["volume_caps"] = caps

        plan = TrainingPlan(**plan_kwargs)  # type: ignore[arg-type]
        _training_plans[str(plan.id)] = plan

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
        """Execute the latest pending training plan."""
        identity = await _resolve_agent(app_state, agent_name)
        agent_id = str(identity.id)

        plan = _find_latest_plan(agent_id)
        if plan is None:
            msg = "No pending training plan found"
            raise NotFoundError(msg)

        # Placeholder: service wiring requires TrainingService
        # in AppState (tracked for future issue).
        msg = "Training execution not yet wired to service layer"
        logger.warning(API_REQUEST_ERROR, error=msg)
        raise NotFoundError(msg)

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
        """Get the latest training result."""
        identity = await _resolve_agent(app_state, agent_name)
        agent_id = str(identity.id)

        result = _training_results.get(agent_id)
        if result is None:
            msg = "No training result found"
            logger.warning(
                API_RESOURCE_NOT_FOUND,
                resource="training_result",
            )
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
        """Preview a training plan (dry run)."""
        identity = await _resolve_agent(app_state, agent_name)
        agent_id = str(identity.id)

        plan = _find_latest_plan(agent_id)
        if plan is None:
            msg = "No pending training plan found"
            raise NotFoundError(msg)

        # Placeholder: service wiring requires TrainingService.
        msg = "Training preview not yet wired to service layer"
        logger.warning(API_REQUEST_ERROR, error=msg)
        raise NotFoundError(msg)

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
        """Update training plan overrides."""
        identity = await _resolve_agent(app_state, agent_name)

        plan = _training_plans.get(plan_id)
        if plan is None:
            msg = "Training plan not found"
            logger.warning(
                API_RESOURCE_NOT_FOUND,
                resource="training_plan",
                plan_id=plan_id,
            )
            raise NotFoundError(msg)

        # Verify plan belongs to the resolved agent.
        if str(plan.new_agent_id) != str(identity.id):
            msg = "Training plan does not belong to this agent"
            raise NotFoundError(msg)

        updates: dict[str, object] = {}
        if data.override_sources is not None:
            updates["override_sources"] = data.override_sources
        caps = _parse_custom_caps(data.custom_caps)
        if caps is not None:
            updates["volume_caps"] = caps

        updated = plan.model_copy(update=updates)
        _training_plans[plan_id] = updated

        return ApiResponse(data=_plan_to_response(updated))


def _find_latest_plan(agent_id: str) -> TrainingPlan | None:
    """Find the latest pending training plan for an agent."""
    for plan in reversed(_training_plans.values()):
        if str(plan.new_agent_id) == agent_id:
            return plan
    return None


def _plan_to_response(plan: TrainingPlan) -> TrainingPlanResponse:
    """Convert a TrainingPlan to a response DTO."""
    return TrainingPlanResponse(
        id=plan.id,
        new_agent_id=plan.new_agent_id,
        new_agent_role=plan.new_agent_role,
        source_selector_type=plan.source_selector_type,
        enabled_content_types=tuple(ct.value for ct in plan.enabled_content_types),
        curation_strategy_type=plan.curation_strategy_type,
        volume_caps=tuple((ct.value, cap) for ct, cap in plan.volume_caps),
        override_sources=plan.override_sources,
        skip_training=plan.skip_training,
        require_review=plan.require_review,
        status=plan.status,
        created_at=plan.created_at,
        executed_at=plan.executed_at,
    )
