"""Agent configuration, performance, activity, and history controller."""

from litestar import Controller, get
from litestar.datastructures import State  # noqa: TC002

from synthorg.api.dto import ApiResponse, PaginatedResponse
from synthorg.api.errors import NotFoundError
from synthorg.api.guards import require_read_access
from synthorg.api.pagination import PaginationLimit, PaginationOffset, paginate
from synthorg.api.path_params import PathName  # noqa: TC001
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.config.schema import AgentConfig  # noqa: TC001
from synthorg.hr.activity import (
    ActivityEvent,
    CareerEvent,
    filter_career_events,
    merge_activity_timeline,
)
from synthorg.hr.performance.summary import (
    AgentPerformanceSummary,
    extract_performance_summary,
)
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_AGENT_ACTIVITY_QUERIED,
    API_AGENT_HISTORY_QUERIED,
    API_AGENT_PERFORMANCE_QUERIED,
    API_RESOURCE_NOT_FOUND,
)

logger = get_logger(__name__)

# Safety cap for lifecycle event queries to prevent unbounded memory
# allocation.  The paginate() helper already caps the returned page
# to MAX_LIMIT, but the underlying fetch is uncapped without this.
_MAX_LIFECYCLE_EVENTS = 10_000


async def _resolve_agent_id(
    app_state: AppState,
    agent_name: str,
) -> str:
    """Resolve an agent name to its ID via the registry.

    Args:
        app_state: Application state with agent registry.
        agent_name: Agent display name.

    Returns:
        Agent ID as string.

    Raises:
        NotFoundError: If the agent is not found in the registry.
    """
    identity = await app_state.agent_registry.get_by_name(agent_name)
    if identity is None:
        msg = "Agent not found"
        logger.warning(API_RESOURCE_NOT_FOUND, resource="agent", name=agent_name)
        raise NotFoundError(msg)
    return str(identity.id)


class AgentController(Controller):
    """Read-only access to agent configurations, performance, activity, and history."""

    path = "/agents"
    tags = ("agents",)
    guards = [require_read_access]  # noqa: RUF012

    @get()
    async def list_agents(
        self,
        state: State,
        offset: PaginationOffset = 0,
        limit: PaginationLimit = 50,
    ) -> PaginatedResponse[AgentConfig]:
        """List all configured agents.

        Args:
            state: Application state.
            offset: Pagination offset.
            limit: Page size.

        Returns:
            Paginated agent configurations.
        """
        app_state: AppState = state.app_state
        agents = await app_state.config_resolver.get_agents()
        page, meta = paginate(agents, offset=offset, limit=limit)
        return PaginatedResponse(data=page, pagination=meta)

    @get("/{agent_name:str}")
    async def get_agent(
        self,
        state: State,
        agent_name: PathName,
    ) -> ApiResponse[AgentConfig]:
        """Get an agent by name.

        Args:
            state: Application state.
            agent_name: Agent name to look up.

        Returns:
            Agent configuration envelope.

        Raises:
            NotFoundError: If the agent is not found.
        """
        app_state: AppState = state.app_state
        agents = await app_state.config_resolver.get_agents()
        name_lower = agent_name.lower()
        for agent in agents:
            if agent.name.lower() == name_lower:
                return ApiResponse(data=agent)
        msg = "Agent not found"
        logger.warning(API_RESOURCE_NOT_FOUND, resource="agent", name=agent_name)
        raise NotFoundError(msg)

    @get("/{agent_name:str}/performance")
    async def get_agent_performance(
        self,
        state: State,
        agent_name: PathName,
    ) -> ApiResponse[AgentPerformanceSummary]:
        """Get an agent's performance summary.

        Args:
            state: Application state.
            agent_name: Agent name to look up.

        Returns:
            Performance summary envelope.

        Raises:
            NotFoundError: If the agent is not found.
        """
        app_state: AppState = state.app_state
        agent_id = await _resolve_agent_id(app_state, agent_name)
        snapshot = await app_state.performance_tracker.get_snapshot(agent_id)
        summary = extract_performance_summary(snapshot, agent_name)
        logger.debug(
            API_AGENT_PERFORMANCE_QUERIED,
            agent_name=agent_name,
            tasks_total=summary.tasks_completed_total,
        )
        return ApiResponse(data=summary)

    @get("/{agent_name:str}/activity")
    async def get_agent_activity(
        self,
        state: State,
        agent_name: PathName,
        offset: PaginationOffset = 0,
        limit: PaginationLimit = 50,
    ) -> PaginatedResponse[ActivityEvent]:
        """Get an agent's activity timeline (paginated).

        Merges lifecycle events and task completion records into
        a single chronological timeline, most recent first.

        Args:
            state: Application state.
            agent_name: Agent name to look up.
            offset: Pagination offset.
            limit: Page size.

        Returns:
            Paginated activity events.

        Raises:
            NotFoundError: If the agent is not found.
        """
        app_state: AppState = state.app_state
        agent_id = await _resolve_agent_id(app_state, agent_name)

        lifecycle_events = await app_state.persistence.lifecycle_events.list_events(
            agent_id=agent_id,
            limit=_MAX_LIFECYCLE_EVENTS,
        )
        task_metrics = app_state.performance_tracker.get_task_metrics(
            agent_id=agent_id,
        )

        timeline = merge_activity_timeline(
            lifecycle_events=lifecycle_events,
            task_metrics=task_metrics,
        )
        page, meta = paginate(timeline, offset=offset, limit=limit)
        logger.debug(
            API_AGENT_ACTIVITY_QUERIED,
            agent_name=agent_name,
            total_events=meta.total,
        )
        return PaginatedResponse(data=page, pagination=meta)

    @get("/{agent_name:str}/history")
    async def get_agent_history(
        self,
        state: State,
        agent_name: PathName,
    ) -> ApiResponse[tuple[CareerEvent, ...]]:
        """Get an agent's career history.

        Returns career-relevant lifecycle events (hired, fired,
        promoted, demoted, onboarded) in chronological order.

        Args:
            state: Application state.
            agent_name: Agent name to look up.

        Returns:
            Career events envelope.

        Raises:
            NotFoundError: If the agent is not found.
        """
        app_state: AppState = state.app_state
        agent_id = await _resolve_agent_id(app_state, agent_name)
        # No limit here: career events are few per agent and the filter
        # below keeps only ~5 event types; capping would risk dropping
        # older milestones (e.g. the original HIRED event).
        events = await app_state.persistence.lifecycle_events.list_events(
            agent_id=agent_id,
        )
        career = filter_career_events(events)
        logger.debug(
            API_AGENT_HISTORY_QUERIED,
            agent_name=agent_name,
            career_events=len(career),
        )
        return ApiResponse(data=career)
