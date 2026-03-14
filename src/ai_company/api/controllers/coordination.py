"""Coordination controller — multi-agent coordination endpoint."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from litestar import Controller, Request, post
from litestar.channels import ChannelsPlugin
from litestar.datastructures import State  # noqa: TC002

from ai_company.api.channels import CHANNEL_TASKS
from ai_company.api.dto import (
    ApiResponse,
    CoordinateTaskRequest,
    CoordinationPhaseResponse,
    CoordinationResultResponse,
)
from ai_company.api.errors import (
    ApiValidationError,
    NotFoundError,
    ServiceUnavailableError,
)
from ai_company.api.guards import require_write_access
from ai_company.api.ws_models import WsEvent, WsEventType
from ai_company.engine.coordination.models import CoordinationContext
from ai_company.engine.errors import CoordinationPhaseError
from ai_company.observability import get_logger
from ai_company.observability.events.api import (
    API_COORDINATION_AGENT_RESOLVE_FAILED,
    API_COORDINATION_COMPLETED,
    API_COORDINATION_FAILED,
    API_COORDINATION_STARTED,
    API_RESOURCE_NOT_FOUND,
)

if TYPE_CHECKING:
    from ai_company.api.state import AppState
    from ai_company.core.agent import AgentIdentity

logger = get_logger(__name__)


def _get_channels_plugin(
    request: Request[Any, Any, Any],
) -> ChannelsPlugin | None:
    """Extract the ChannelsPlugin from the application, or None."""
    for plugin in request.app.plugins:
        if isinstance(plugin, ChannelsPlugin):
            return plugin
    return None


def _publish_ws_event(
    request: Request[Any, Any, Any],
    event_type: WsEventType,
    payload: dict[str, object],
) -> None:
    """Best-effort publish a coordination event to the tasks channel."""
    channels_plugin = _get_channels_plugin(request)
    if channels_plugin is None:
        return

    event = WsEvent(
        event_type=event_type,
        channel=CHANNEL_TASKS,
        timestamp=datetime.now(UTC),
        payload=payload,
    )
    try:
        channels_plugin.publish(
            event.model_dump_json(),
            channels=[CHANNEL_TASKS],
        )
    except MemoryError, RecursionError:
        raise
    except Exception:
        logger.warning(
            API_COORDINATION_FAILED,
            note="Failed to publish WebSocket event",
            event_type=event_type.value,
            exc_info=True,
        )


class CoordinationController(Controller):
    """Multi-agent coordination endpoint."""

    path = "/tasks/{task_id:str}/coordinate"
    tags = ("coordination",)

    @post(guards=[require_write_access], status_code=200)
    async def coordinate_task(
        self,
        request: Request[Any, Any, Any],
        state: State,
        task_id: str,
        data: CoordinateTaskRequest,
    ) -> ApiResponse[CoordinationResultResponse]:
        """Trigger multi-agent coordination for a task.

        Args:
            request: The incoming request.
            state: Application state.
            task_id: Task identifier.
            data: Coordination request payload.

        Returns:
            Coordination result envelope.

        Raises:
            NotFoundError: If the task is not found.
            ApiValidationError: If agent resolution fails.
            ServiceUnavailableError: If coordinator not configured.
        """
        app_state: AppState = state.app_state

        # Ensure coordinator is configured
        if not app_state.has_coordinator:
            msg = "Coordinator not configured"
            raise ServiceUnavailableError(msg)

        # 1. Get task
        task = await app_state.task_engine.get_task(task_id)
        if task is None:
            logger.warning(
                API_RESOURCE_NOT_FOUND,
                resource="task",
                id=task_id,
            )
            msg = f"Task {task_id!r} not found"
            raise NotFoundError(msg)

        # 2. Resolve agents
        agents = await self._resolve_agents(app_state, data, task_id)

        # 3. Build coordination config
        coord_config = app_state.config.coordination.to_coordination_config(
            max_concurrency_per_wave=data.max_concurrency_per_wave,
            fail_fast=data.fail_fast,
        )

        # 4. Build coordination context
        from ai_company.engine.decomposition.models import (  # noqa: PLC0415
            DecompositionContext,
        )

        context = CoordinationContext(
            task=task,
            available_agents=agents,
            decomposition_context=DecompositionContext(
                max_subtasks=data.max_subtasks,
            ),
            config=coord_config,
        )

        # 5. Publish start event
        _publish_ws_event(
            request,
            WsEventType.COORDINATION_STARTED,
            {
                "task_id": task_id,
                "agent_count": len(agents),
            },
        )

        logger.info(
            API_COORDINATION_STARTED,
            task_id=task_id,
            agent_count=len(agents),
        )

        # 6. Execute coordination
        try:
            result = await app_state.coordinator.coordinate(context)
        except CoordinationPhaseError as exc:
            logger.warning(
                API_COORDINATION_FAILED,
                task_id=task_id,
                phase=exc.phase,
                error=str(exc),
            )
            _publish_ws_event(
                request,
                WsEventType.COORDINATION_FAILED,
                {
                    "task_id": task_id,
                    "phase": exc.phase,
                    "error": str(exc),
                },
            )
            raise ApiValidationError(str(exc)) from exc

        # 7. Publish completion event
        ws_event_type = (
            WsEventType.COORDINATION_COMPLETED
            if result.is_success
            else WsEventType.COORDINATION_FAILED
        )
        _publish_ws_event(
            request,
            ws_event_type,
            {
                "task_id": task_id,
                "topology": result.topology.value,
                "is_success": result.is_success,
                "total_duration_seconds": result.total_duration_seconds,
            },
        )

        logger.info(
            API_COORDINATION_COMPLETED,
            task_id=task_id,
            topology=result.topology.value,
            is_success=result.is_success,
            total_duration_seconds=result.total_duration_seconds,
        )

        # 8. Map to response
        response = CoordinationResultResponse(
            parent_task_id=result.parent_task_id,
            topology=result.topology.value,
            is_success=result.is_success,
            total_duration_seconds=result.total_duration_seconds,
            total_cost_usd=result.total_cost_usd,
            phases=tuple(
                CoordinationPhaseResponse(
                    phase=p.phase,
                    success=p.success,
                    duration_seconds=p.duration_seconds,
                    error=p.error,
                )
                for p in result.phases
            ),
            wave_count=len(result.waves),
        )
        return ApiResponse(data=response)

    async def _resolve_agents(
        self,
        app_state: AppState,
        data: CoordinateTaskRequest,
        task_id: str,
    ) -> tuple[AgentIdentity, ...]:
        """Resolve agent identities from request or registry.

        Args:
            app_state: Application state.
            data: Coordination request with optional agent names.
            task_id: Task ID for logging.

        Returns:
            Tuple of agent identities.

        Raises:
            ApiValidationError: If agents cannot be resolved.
        """
        registry = app_state.agent_registry

        if data.agent_names is not None:
            agents: list[AgentIdentity] = []
            for name in data.agent_names:
                agent = await registry.get_by_name(name)
                if agent is None:
                    logger.warning(
                        API_COORDINATION_AGENT_RESOLVE_FAILED,
                        task_id=task_id,
                        agent_name=name,
                    )
                    msg = f"Agent {name!r} not found"
                    raise ApiValidationError(msg)
                agents.append(agent)
            return tuple(agents)

        active_agents = await registry.list_active()
        if not active_agents:
            logger.warning(
                API_COORDINATION_AGENT_RESOLVE_FAILED,
                task_id=task_id,
                error="No active agents available",
            )
            msg = "No active agents available for coordination"
            raise ApiValidationError(msg)
        return active_agents
