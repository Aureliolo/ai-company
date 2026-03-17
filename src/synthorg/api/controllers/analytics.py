"""Analytics controller — derived read-only metrics."""

import asyncio
from collections import Counter

from litestar import Controller, get
from litestar.datastructures import State  # noqa: TC002
from pydantic import BaseModel, ConfigDict, Field

from synthorg.api.dto import ApiResponse
from synthorg.api.guards import require_read_access
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.core.enums import TaskStatus
from synthorg.observability import get_logger
from synthorg.observability.events.api import API_REQUEST_ERROR

logger = get_logger(__name__)


class OverviewMetrics(BaseModel):
    """High-level analytics overview.

    Attributes:
        total_tasks: Total number of tasks.
        tasks_by_status: Task counts grouped by status.
        total_agents: Number of configured agents.
        total_cost_usd: Total cost across all records.
    """

    model_config = ConfigDict(frozen=True)

    total_tasks: int = Field(ge=0, description="Total number of tasks")
    tasks_by_status: dict[str, int] = Field(
        description="Task counts by status (keys are TaskStatus values)",
    )
    total_agents: int = Field(ge=0, description="Number of configured agents")
    total_cost_usd: float = Field(ge=0.0, description="Total cost in USD")


class AnalyticsController(Controller):
    """Derived analytics and metrics."""

    path = "/analytics"
    tags = ("analytics",)

    @get("/overview", guards=[require_read_access])
    async def get_overview(
        self,
        state: State,
    ) -> ApiResponse[OverviewMetrics]:
        """Return high-level metrics overview.

        Args:
            state: Application state.

        Returns:
            Overview metrics envelope.
        """
        app_state: AppState = state.app_state

        try:
            async with asyncio.TaskGroup() as tg:
                t_tasks = tg.create_task(app_state.persistence.tasks.list_tasks())
                t_cost = tg.create_task(app_state.cost_tracker.get_total_cost())
                t_agents = tg.create_task(app_state.config_resolver.get_agents())
        except ExceptionGroup as eg:
            logger.warning(
                API_REQUEST_ERROR,
                endpoint="analytics.overview",
                error_count=len(eg.exceptions),
                exc_info=True,
            )
            raise eg.exceptions[0] from eg

        all_tasks = t_tasks.result()
        counts = Counter(t.status.value for t in all_tasks)
        by_status = {s.value: counts.get(s.value, 0) for s in TaskStatus}

        return ApiResponse(
            data=OverviewMetrics(
                total_tasks=len(all_tasks),
                tasks_by_status=by_status,
                total_agents=len(t_agents.result()),
                total_cost_usd=t_cost.result(),
            ),
        )
