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
from synthorg.api.errors import NotFoundError
from synthorg.api.guards import require_org_mutation, require_read_access
from synthorg.api.path_params import PathName  # noqa: TC001
from synthorg.api.state import AppState  # noqa: TC001
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
_training_results: dict[str, object] = {}


class TrainingController(Controller):
    """Training mode API endpoints.

    Path prefix: ``/api/v1/agents/{agent_name:str}/training``
    """

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
        """Create a training plan for an agent.

        Args:
            app_state: Application state.
            agent_name: Agent display name.
            data: Plan creation request.

        Returns:
            Created training plan.
        """
        identity = await app_state.agent_registry.get_by_name(
            agent_name,
        )
        if identity is None:
            msg = "Agent not found"
            logger.warning(
                API_RESOURCE_NOT_FOUND,
                resource="agent",
                name=str(agent_name),
            )
            raise NotFoundError(msg)

        enabled_types = (
            frozenset(ContentType(ct) for ct in data.content_types)
            if data.content_types
            else frozenset(ContentType)
        )

        volume_caps_kwarg: dict[str, object] = {}
        if data.custom_caps:
            volume_caps_kwarg["volume_caps"] = tuple(
                (ContentType(k), v) for k, v in data.custom_caps.items()
            )

        plan = TrainingPlan(
            new_agent_id=str(identity.id),
            new_agent_role=str(identity.role),
            new_agent_level=identity.level,
            override_sources=data.override_sources,
            enabled_content_types=enabled_types,
            skip_training=data.skip_training,
            require_review=data.require_review,
            created_at=datetime.now(UTC),
            **volume_caps_kwarg,  # type: ignore[arg-type]
        )

        _training_plans[str(plan.id)] = plan

        logger.info(
            HR_TRAINING_PLAN_CREATED,
            plan_id=str(plan.id),
            agent_name=str(agent_name),
        )

        return ApiResponse(
            data=_plan_to_response(plan),
        )

    @post(
        "/execute",
        guards=[require_org_mutation()],
        status_code=HTTP_200_OK,
    )
    async def execute_plan(
        self,
        app_state: AppState,  # noqa: ARG002
        agent_name: PathName,  # noqa: ARG002
    ) -> ApiResponse[TrainingResultResponse]:
        """Execute the latest training plan.

        Returns:
            Training result.
        """
        # Placeholder: would find latest plan and execute
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
        app_state: AppState,  # noqa: ARG002
        agent_name: PathName,  # noqa: ARG002
    ) -> ApiResponse[TrainingResultResponse]:
        """Get the latest training result.

        Returns:
            Training result.
        """
        msg = "No training result found"
        logger.warning(API_RESOURCE_NOT_FOUND, resource="training_result")
        raise NotFoundError(msg)

    @post(
        "/preview",
        guards=[require_read_access],
        status_code=HTTP_200_OK,
    )
    async def preview_plan(
        self,
        app_state: AppState,  # noqa: ARG002
        agent_name: PathName,  # noqa: ARG002
    ) -> ApiResponse[TrainingResultResponse]:
        """Preview a training plan (dry run).

        Returns:
            Preview result with extraction/curation counts.
        """
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
        app_state: AppState,  # noqa: ARG002
        agent_name: PathName,  # noqa: ARG002
        plan_id: str,
        data: UpdateTrainingOverridesRequest,
    ) -> ApiResponse[TrainingPlanResponse]:
        """Update training plan overrides.

        Args:
            app_state: Application state.
            agent_name: Agent display name.
            plan_id: Training plan ID.
            data: Override updates.

        Returns:
            Updated training plan.
        """
        plan = _training_plans.get(plan_id)
        if plan is None:
            msg = "Training plan not found"
            logger.warning(
                API_RESOURCE_NOT_FOUND,
                resource="training_plan",
                plan_id=plan_id,
            )
            raise NotFoundError(msg)

        updates: dict[str, object] = {}
        if data.override_sources is not None:
            updates["override_sources"] = data.override_sources
        if data.custom_caps is not None:
            updates["volume_caps"] = tuple(
                (ContentType(k), v) for k, v in data.custom_caps.items()
            )

        updated = plan.model_copy(update=updates)
        _training_plans[plan_id] = updated

        return ApiResponse(
            data=_plan_to_response(updated),
        )


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
