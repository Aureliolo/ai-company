"""Org-wide activity feed controller."""

import asyncio
from datetime import UTC, datetime, timedelta
from enum import IntEnum
from typing import TYPE_CHECKING, Annotated

if TYPE_CHECKING:
    from collections.abc import Awaitable

from litestar import Controller, get
from litestar.datastructures import State  # noqa: TC002
from litestar.params import Parameter

from synthorg.api.dto import PaginatedResponse
from synthorg.api.errors import ServiceUnavailableError
from synthorg.api.guards import require_read_access
from synthorg.api.pagination import PaginationLimit, PaginationOffset, paginate
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.budget.cost_record import CostRecord  # noqa: TC001
from synthorg.budget.currency import DEFAULT_CURRENCY
from synthorg.communication.delegation.models import DelegationRecord  # noqa: TC001
from synthorg.hr.activity import (
    ActivityEvent,
    merge_activity_timeline,
)
from synthorg.hr.performance.models import TaskMetricRecord  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.api import (
    API_ACTIVITY_FEED_QUERIED,
    API_REQUEST_ERROR,
)
from synthorg.tools.invocation_record import ToolInvocationRecord  # noqa: TC001

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

        Merges lifecycle events, task metrics, cost records, tool
        invocations, and delegation records into a unified
        chronological timeline, most recent first.  Non-lifecycle
        data sources degrade gracefully when unavailable.

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

        lifecycle_events = await app_state.persistence.lifecycle_events.list_events(
            agent_id=agent_id,
            since=since,
            limit=_MAX_LIFECYCLE_EVENTS,
        )

        task_metrics = _fetch_task_metrics(app_state, agent_id, since, now)
        try:
            async with asyncio.TaskGroup() as tg:
                cost_task = tg.create_task(
                    _fetch_cost_records(app_state, agent_id, since, now),
                )
                tool_task = tg.create_task(
                    _fetch_tool_invocations(app_state, agent_id, since, now),
                )
                del_task = tg.create_task(
                    _fetch_delegation_records(app_state, agent_id, since, now),
                )
        except ExceptionGroup as eg:
            fatal = eg.subgroup((MemoryError, RecursionError))
            if fatal is not None:
                raise fatal from eg
            svc = eg.subgroup(ServiceUnavailableError)
            if svc is not None:
                raise svc from eg
            logger.warning(
                API_REQUEST_ERROR,
                endpoint="activities",
                error_count=len(eg.exceptions),
                exc_info=True,
            )
            cost_task = tool_task = del_task = None  # type: ignore[assignment]
        cost_records = cost_task.result() if cost_task is not None else ()
        tool_invocations = tool_task.result() if tool_task is not None else ()
        if del_task is not None:
            sent, received = del_task.result()
        else:
            sent, received = (), ()

        try:
            budget_cfg = await app_state.config_resolver.get_budget_config()
            currency = budget_cfg.currency
        except Exception:
            logger.warning(
                API_REQUEST_ERROR,
                endpoint="activities",
                detail="budget config unavailable, using default currency",
                exc_info=True,
            )
            currency = DEFAULT_CURRENCY
        timeline = merge_activity_timeline(
            lifecycle_events=lifecycle_events,
            task_metrics=task_metrics,
            cost_records=cost_records,
            tool_invocations=tool_invocations,
            delegation_records_sent=sent,
            delegation_records_received=received,
            currency=currency,
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


# ── Data source fetchers (graceful degradation) ──────────────────


def _fetch_task_metrics(
    app_state: AppState,
    agent_id: str | None,
    since: datetime,
    now: datetime,
) -> tuple[TaskMetricRecord, ...]:
    """Fetch task metrics, falling back to empty on failure."""
    try:
        return app_state.performance_tracker.get_task_metrics(
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
        return ()


async def _fetch_cost_records(
    app_state: AppState,
    agent_id: str | None,
    since: datetime,
    now: datetime,
) -> tuple[CostRecord, ...]:
    """Fetch cost records, falling back to empty on failure."""
    if not app_state.has_cost_tracker:
        return ()
    try:
        return await app_state.cost_tracker.get_records(
            agent_id=agent_id,
            start=since,
            end=now,
        )
    except MemoryError, RecursionError:
        raise
    except ServiceUnavailableError:
        raise
    except Exception:
        logger.warning(
            API_REQUEST_ERROR,
            endpoint="activities",
            error="cost_tracker_unavailable",
            exc_info=True,
        )
        return ()


async def _fetch_tool_invocations(
    app_state: AppState,
    agent_id: str | None,
    since: datetime,
    now: datetime,
) -> tuple[ToolInvocationRecord, ...]:
    """Fetch tool invocation records, falling back to empty on failure."""
    if not app_state.has_tool_invocation_tracker:
        return ()
    try:
        return await app_state.tool_invocation_tracker.get_records(
            agent_id=agent_id,
            start=since,
            end=now,
        )
    except MemoryError, RecursionError:
        raise
    except ServiceUnavailableError:
        raise
    except Exception:
        logger.warning(
            API_REQUEST_ERROR,
            endpoint="activities",
            error="tool_invocation_tracker_unavailable",
            exc_info=True,
        )
        return ()


async def _safe_delegation_query(
    coro: Awaitable[tuple[DelegationRecord, ...]],
    error_label: str,
) -> tuple[DelegationRecord, ...]:
    """Run a delegation store query with graceful degradation."""
    try:
        return await coro
    except MemoryError, RecursionError:
        raise
    except ServiceUnavailableError:
        raise
    except Exception:
        logger.warning(
            API_REQUEST_ERROR,
            endpoint="activities",
            error=error_label,
            exc_info=True,
        )
        return ()


async def _fetch_delegation_records(
    app_state: AppState,
    agent_id: str | None,
    since: datetime,
    now: datetime,
) -> tuple[tuple[DelegationRecord, ...], tuple[DelegationRecord, ...]]:
    """Fetch delegation records (sent + received), falling back to empty.

    Returns:
        ``(sent, received)`` tuples of delegation records.
    """
    if not app_state.has_delegation_record_store:
        return (), ()
    store = app_state.delegation_record_store
    if agent_id is None:
        # Org-wide: each record generates both perspectives.
        all_records = await _safe_delegation_query(
            store.get_all_records(start=since, end=now),
            "delegation_record_store_unavailable",
        )
        return all_records, all_records

    # Agent-specific: fetch each perspective independently so a
    # failure in one does not discard the other.
    sent = await _safe_delegation_query(
        store.get_records_as_delegator(agent_id, start=since, end=now),
        "delegation_delegator_query_failed",
    )
    received = await _safe_delegation_query(
        store.get_records_as_delegatee(agent_id, start=since, end=now),
        "delegation_delegatee_query_failed",
    )
    return sent, received
