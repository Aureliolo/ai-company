"""Org-wide activity feed controller."""

from datetime import UTC, datetime, timedelta
from enum import IntEnum
from typing import Annotated

from litestar import Controller, get
from litestar.datastructures import State  # noqa: TC002
from litestar.params import Parameter

from synthorg.api.dto import PaginatedResponse
from synthorg.api.errors import ServiceUnavailableError
from synthorg.api.guards import require_read_access
from synthorg.api.pagination import PaginationLimit, PaginationOffset, paginate
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.hr.activity import (
    ActivityEvent,
    merge_activity_timeline,
)
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_ACTIVITY_FEED_QUERIED,
    API_REQUEST_ERROR,
)

logger = get_logger(__name__)

# Safety cap for unbounded lifecycle event queries.
_MAX_LIFECYCLE_EVENTS = 10_000


class ActivityWindowHours(IntEnum):
    """Allowed time windows for the activity feed."""

    DAY = 24
    TWO_DAYS = 48
    WEEK = 168


class ActivityController(Controller):
    """Org-wide activity feed (REST fallback for WebSocket)."""

    path = "/activities"
    tags = ("activities",)
    guards = [require_read_access]  # noqa: RUF012

    @get()
    async def list_activities(  # noqa: PLR0913
        self,
        state: State,
        offset: PaginationOffset = 0,
        limit: PaginationLimit = 50,
        event_type: Annotated[
            str | None,
            Parameter(
                query="type",
                max_length=64,
                description="Filter by event_type",
            ),
        ] = None,
        agent_id: Annotated[
            str | None,
            Parameter(
                max_length=128,
                description="Filter by agent_id",
            ),
        ] = None,
        last_n_hours: Annotated[
            ActivityWindowHours,
            Parameter(description="Time window (24, 48, or 168 hours)"),
        ] = ActivityWindowHours.DAY,
    ) -> PaginatedResponse[ActivityEvent]:
        """Return a paginated org-wide activity feed.

        Merges lifecycle events and task completion records into
        a unified chronological timeline, most recent first.
        If the performance tracker is unavailable, task metrics
        are omitted (lifecycle events are still returned).

        Args:
            state: Application state.
            offset: Pagination offset.
            limit: Page size.
            event_type: Filter by event_type (e.g. ``"hired"``).
            agent_id: Filter events for a specific agent.
            last_n_hours: Time window in hours (24, 48, or 168).

        Returns:
            Paginated activity events.
        """
        app_state: AppState = state.app_state
        now = datetime.now(UTC)
        since = now - timedelta(hours=last_n_hours)

        # Lifecycle events (async), then task metrics (sync)
        lifecycle_events = await app_state.persistence.lifecycle_events.list_events(
            agent_id=agent_id,
            since=since,
            limit=_MAX_LIFECYCLE_EVENTS,
        )

        try:
            task_metrics = app_state.performance_tracker.get_task_metrics(
                agent_id=agent_id,
                since=since,
                until=now,
            )
        except MemoryError, RecursionError:
            raise
        except ServiceUnavailableError:
            raise
        except Exception:
            logger.warning(
                API_REQUEST_ERROR,
                endpoint="activities",
                error="performance_tracker_unavailable",
                exc_info=True,
            )
            task_metrics = ()

        timeline = merge_activity_timeline(
            lifecycle_events=lifecycle_events,
            task_metrics=task_metrics,
        )

        if event_type is not None:
            timeline = tuple(e for e in timeline if e.event_type == event_type)

        page, meta = paginate(timeline, offset=offset, limit=limit)

        logger.debug(
            API_ACTIVITY_FEED_QUERIED,
            total_events=meta.total,
            type_filter=event_type,
            agent_id_filter=agent_id,
            last_n_hours=last_n_hours,
        )

        return PaginatedResponse(data=page, pagination=meta)
