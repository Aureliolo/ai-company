"""Coordination metrics query controller.

Exposes ``GET /coordination/metrics`` for querying stored
coordination metrics from completed multi-agent runs.
"""

from datetime import datetime  # noqa: TC003
from typing import Annotated

from litestar import Controller, get
from litestar.datastructures import State  # noqa: TC002
from litestar.params import Parameter

from synthorg.api.dto import PaginatedResponse
from synthorg.api.guards import require_read_access
from synthorg.api.pagination import (
    PaginationLimit,
    PaginationOffset,
    paginate,
)
from synthorg.api.path_params import QUERY_MAX_LENGTH
from synthorg.budget.coordination_store import CoordinationMetricsRecord
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_COORDINATION_METRICS_QUERIED,
)

logger = get_logger(__name__)


class CoordinationMetricsController(Controller):
    """Query coordination metrics from completed runs."""

    path = "/coordination/metrics"
    tags = ("coordination",)
    guards = [require_read_access]  # noqa: RUF012

    @get()
    async def list_coordination_metrics(  # noqa: PLR0913
        self,
        state: State,
        task_id: Annotated[str, Parameter(max_length=QUERY_MAX_LENGTH)] | None = None,
        agent_id: Annotated[str, Parameter(max_length=QUERY_MAX_LENGTH)] | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        offset: PaginationOffset = 0,
        limit: PaginationLimit = 50,
    ) -> PaginatedResponse[CoordinationMetricsRecord]:
        """Query coordination metrics with optional filters.

        All filters are AND-combined.  Results are newest-first.
        """
        app_state = state.app_state
        entries = app_state.coordination_metrics_store.query(
            task_id=task_id,
            agent_id=agent_id,
            since=since,
            until=until,
        )
        page, meta = paginate(entries, offset=offset, limit=limit)
        logger.info(
            API_COORDINATION_METRICS_QUERIED,
            total=meta.total,
            offset=meta.offset,
            limit=meta.limit,
        )
        return PaginatedResponse[CoordinationMetricsRecord](
            data=page,
            pagination=meta,
        )
