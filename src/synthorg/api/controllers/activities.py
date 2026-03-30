"""Org-wide activity feed controller."""

import asyncio
from datetime import UTC, datetime, timedelta
from enum import IntEnum
from typing import TYPE_CHECKING, Annotated, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from synthorg.hr.models import AgentLifecycleEvent

from litestar import Controller, Request, get
from litestar.datastructures import State  # noqa: TC002
from litestar.params import Parameter

from synthorg.api.auth.models import AuthenticatedUser
from synthorg.api.dto import PaginatedResponse
from synthorg.api.errors import ServiceUnavailableError
from synthorg.api.guards import _WRITE_ROLES, require_read_access
from synthorg.api.pagination import PaginationLimit, PaginationOffset, paginate
from synthorg.api.state import AppState  # noqa: TC001
from synthorg.budget.cost_record import CostRecord  # noqa: TC001
from synthorg.budget.currency import DEFAULT_CURRENCY
from synthorg.communication.delegation.models import DelegationRecord  # noqa: TC001
from synthorg.hr.activity import (
    ActivityEvent,
    merge_activity_timeline,
    redact_cost_events,
)
from synthorg.hr.enums import ActivityEventType  # noqa: TC001
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

# Degraded source names -- used in responses and tests.
_SRC_PERFORMANCE_TRACKER = "performance_tracker"
_SRC_COST_TRACKER = "cost_tracker"
_SRC_TOOL_INVOCATION_TRACKER = "tool_invocation_tracker"
_SRC_DELEGATION_RECORD_STORE = "delegation_record_store"
_SRC_BUDGET_CONFIG = "budget_config"


class ActivityWindowHours(IntEnum):
    """Allowed time windows for the activity feed."""

    DAY = 24
    TWO_DAYS = 48
    WEEK = 168


async def _build_timeline(  # noqa: C901, PLR0912, PLR0915
    app_state: AppState,
    lifecycle_events: tuple[AgentLifecycleEvent, ...],
    agent_id: str | None,
    since: datetime,
    now: datetime,
) -> tuple[tuple[ActivityEvent, ...], list[str]]:
    """Fetch all data sources and merge into a timeline.

    Returns:
        ``(timeline, degraded_sources)`` where ``degraded_sources``
        lists the names of data sources that failed.
    """
    degraded: list[str] = []

    task_metrics, tm_degraded = _fetch_task_metrics(
        app_state,
        agent_id,
        since,
        now,
    )
    if tm_degraded:
        degraded.append(_SRC_PERFORMANCE_TRACKER)

    cost_task: asyncio.Task[tuple[tuple[CostRecord, ...], bool]] | None = None
    tool_task: asyncio.Task[tuple[tuple[ToolInvocationRecord, ...], bool]] | None = None
    del_task: (
        asyncio.Task[
            tuple[
                tuple[DelegationRecord, ...],
                tuple[DelegationRecord, ...],
                bool,
            ]
        ]
        | None
    ) = None
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
        cost_task = tool_task = del_task = None
        degraded.extend(
            [
                _SRC_COST_TRACKER,
                _SRC_TOOL_INVOCATION_TRACKER,
                _SRC_DELEGATION_RECORD_STORE,
            ]
        )

    if cost_task is not None:
        cost_records, cost_deg = cost_task.result()
        if cost_deg:
            degraded.append(_SRC_COST_TRACKER)
    else:
        cost_records = ()

    if tool_task is not None:
        tool_invocations, tool_deg = tool_task.result()
        if tool_deg:
            degraded.append(_SRC_TOOL_INVOCATION_TRACKER)
    else:
        tool_invocations = ()

    if del_task is not None:
        sent, received, del_deg = del_task.result()
        if del_deg:
            degraded.append(_SRC_DELEGATION_RECORD_STORE)
    else:
        sent, received = (), ()

    try:
        budget_cfg = await app_state.config_resolver.get_budget_config()
        currency = budget_cfg.currency
    except MemoryError, RecursionError:
        raise
    except ServiceUnavailableError:
        raise
    except Exception:
        logger.warning(
            API_REQUEST_ERROR,
            endpoint="activities",
            detail="budget config unavailable, using default currency",
            exc_info=True,
        )
        currency = DEFAULT_CURRENCY
        degraded.append(_SRC_BUDGET_CONFIG)

    timeline = merge_activity_timeline(
        lifecycle_events=lifecycle_events,
        task_metrics=task_metrics,
        cost_records=cost_records,
        tool_invocations=tool_invocations,
        delegation_records_sent=sent,
        delegation_records_received=received,
        currency=currency,
    )
    return timeline, degraded


class ActivityController(Controller):
    """Org-wide activity feed (REST fallback for WebSocket)."""

    path = "/activities"
    tags = ("activities",)
    guards = [require_read_access]  # noqa: RUF012

    @get()
    async def list_activities(  # noqa: PLR0913
        self,
        request: Request[Any, Any, Any],
        state: State,
        offset: PaginationOffset = 0,
        limit: PaginationLimit = 50,
        event_type: Annotated[
            ActivityEventType | None,
            Parameter(
                query="type",
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
            request: Incoming HTTP request (used for role-based redaction).
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

        timeline, degraded = await _build_timeline(
            app_state,
            lifecycle_events,
            agent_id,
            since,
            now,
        )

        if event_type is not None:
            timeline = tuple(e for e in timeline if e.event_type == event_type)

        # Redact cost details unless the user has a write role.
        # Fail-closed: redact by default if auth identity is missing.
        auth_user = request.scope.get("user")
        if not (
            isinstance(auth_user, AuthenticatedUser) and auth_user.role in _WRITE_ROLES
        ):
            timeline = redact_cost_events(timeline)

        page, meta = paginate(timeline, offset=offset, limit=limit)

        logger.debug(
            API_ACTIVITY_FEED_QUERIED,
            total_events=meta.total,
            type_filter=event_type,
            agent_id_filter=agent_id,
            last_n_hours=last_n_hours,
        )

        return PaginatedResponse(
            data=page,
            pagination=meta,
            degraded_sources=tuple(degraded),
        )


# ── Data source fetchers (graceful degradation) ──────────────────


def _fetch_task_metrics(
    app_state: AppState,
    agent_id: str | None,
    since: datetime,
    now: datetime,
) -> tuple[tuple[TaskMetricRecord, ...], bool]:
    """Fetch task metrics, falling back to empty on failure.

    Returns:
        ``(records, is_degraded)`` tuple.
    """
    try:
        return app_state.performance_tracker.get_task_metrics(
            agent_id=agent_id,
            since=since,
            until=now,
        ), False
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
        return (), True


async def _fetch_cost_records(
    app_state: AppState,
    agent_id: str | None,
    since: datetime,
    now: datetime,
) -> tuple[tuple[CostRecord, ...], bool]:
    """Fetch cost records, falling back to empty on failure.

    Returns:
        ``(records, is_degraded)`` tuple.
    """
    if not app_state.has_cost_tracker:
        return (), False
    try:
        return await app_state.cost_tracker.get_records(
            agent_id=agent_id,
            start=since,
            end=now,
        ), False
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
        return (), True


async def _fetch_tool_invocations(
    app_state: AppState,
    agent_id: str | None,
    since: datetime,
    now: datetime,
) -> tuple[tuple[ToolInvocationRecord, ...], bool]:
    """Fetch tool invocation records, falling back to empty on failure.

    Returns:
        ``(records, is_degraded)`` tuple.
    """
    if not app_state.has_tool_invocation_tracker:
        return (), False
    try:
        return await app_state.tool_invocation_tracker.get_records(
            agent_id=agent_id,
            start=since,
            end=now,
        ), False
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
        return (), True


async def _safe_delegation_query(
    coro: Awaitable[tuple[DelegationRecord, ...]],
    error_label: str,
) -> tuple[tuple[DelegationRecord, ...], bool]:
    """Run a delegation store query with graceful degradation.

    Returns:
        ``(records, is_degraded)`` tuple.
    """
    try:
        return (await coro), False
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
        return (), True


async def _fetch_delegation_records(
    app_state: AppState,
    agent_id: str | None,
    since: datetime,
    now: datetime,
) -> tuple[
    tuple[DelegationRecord, ...],
    tuple[DelegationRecord, ...],
    bool,
]:
    """Fetch delegation records (sent + received), falling back to empty.

    Returns:
        ``(sent, received, is_degraded)`` tuple.
    """
    if not app_state.has_delegation_record_store:
        return (), (), False
    store = app_state.delegation_record_store
    if agent_id is None:
        # Org-wide: each record generates both perspectives.
        all_records, degraded = await _safe_delegation_query(
            store.get_all_records(start=since, end=now),
            "delegation_record_store_unavailable",
        )
        return all_records, all_records, degraded

    # Agent-specific: fetch each perspective independently so a
    # failure in one does not discard the other.
    sent, sent_deg = await _safe_delegation_query(
        store.get_records_as_delegator(agent_id, start=since, end=now),
        "delegation_delegator_query_failed",
    )
    received, recv_deg = await _safe_delegation_query(
        store.get_records_as_delegatee(agent_id, start=since, end=now),
        "delegation_delegatee_query_failed",
    )
    return sent, received, sent_deg or recv_deg
