"""Agent activity feed service.

Aggregates the multiple activity sources that ``activity.py`` already
knows how to merge (lifecycle events, task metrics, cost records,
tool invocations, delegation records) into a single call per agent.
MCP handlers use this service to shim
``synthorg_agents_get_activity`` without reimplementing the
multi-source merge in the handler layer.

The REST activity controller (``api/controllers/activities.py``)
keeps its own richer implementation because it also owns the
graceful-degradation + role-based cost redaction that are specific
to the HTTP surface. Those concerns are intentionally not mirrored
here; MCP callers are already admin-scoped.

A task-scoped entry point (``get_task_activity``) is a planned
extension on the same class for the task-centric MCP tools.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from synthorg.budget.currency import DEFAULT_CURRENCY
from synthorg.core.types import NotBlankStr  # noqa: TC001 -- runtime annotation
from synthorg.hr.activity import ActivityEvent, merge_activity_timeline
from synthorg.observability import get_logger
from synthorg.observability.events.hr import HR_ACTIVITY_AGENT_FETCHED

if TYPE_CHECKING:
    from synthorg.budget.tracker import CostTracker
    from synthorg.communication.delegation.record_store import DelegationRecordStore
    from synthorg.hr.performance.tracker import PerformanceTracker
    from synthorg.hr.persistence_protocol import LifecycleEventRepository
    from synthorg.tools.invocation_tracker import ToolInvocationTracker


logger = get_logger(__name__)

_DEFAULT_WINDOW_HOURS: int = 168  # 7 days -- matches API controller cap.
_LIFECYCLE_CAP: int = 1000


class ActivityFeedService:
    """Aggregates multi-source activity for a single agent.

    Constructor dependencies are injected individually so MCP bootstrap
    can wire whichever sources the current deployment has available.
    The optional sources (cost / tool invocation / delegation) default
    to ``None``; missing sources are silently skipped.
    """

    __slots__ = (
        "_cost_tracker",
        "_delegation_store",
        "_lifecycle_repo",
        "_performance_tracker",
        "_tool_invocation_tracker",
    )

    def __init__(
        self,
        *,
        performance_tracker: PerformanceTracker,
        lifecycle_repo: LifecycleEventRepository,
        cost_tracker: CostTracker | None = None,
        tool_invocation_tracker: ToolInvocationTracker | None = None,
        delegation_store: DelegationRecordStore | None = None,
    ) -> None:
        """Initialise with the required + optional sources."""
        self._performance_tracker = performance_tracker
        self._lifecycle_repo = lifecycle_repo
        self._cost_tracker = cost_tracker
        self._tool_invocation_tracker = tool_invocation_tracker
        self._delegation_store = delegation_store

    async def get_agent_activity(
        self,
        agent_id: NotBlankStr,
        *,
        offset: int,
        limit: int,
        window_hours: int = _DEFAULT_WINDOW_HOURS,
    ) -> tuple[tuple[ActivityEvent, ...], int]:
        """Return a page of activity events for *agent_id* + the total count.

        Events are newest-first (via
        :func:`merge_activity_timeline`). The total reported is the
        full merged timeline length for the window, so pagination
        metadata stays consistent even when the page is short.

        Args:
            agent_id: Agent whose activity to fetch.
            offset: Page offset (>= 0).
            limit: Page size (> 0).
            window_hours: Time window in hours; defaults to 168 (7d).

        Returns:
            Tuple of ``(page, total)``.
        """
        now = datetime.now(UTC)
        since = now - timedelta(hours=window_hours)
        agent_key = str(agent_id)

        lifecycle_events = await self._lifecycle_repo.list_events(
            agent_id=agent_key,
            since=since,
            limit=_LIFECYCLE_CAP,
        )
        task_metrics = self._performance_tracker.get_task_metrics(
            agent_id=agent_key,
            since=since,
            until=now,
        )

        async with asyncio.TaskGroup() as tg:
            cost_task = tg.create_task(
                self._fetch_costs(agent_key, since, now),
            )
            tool_task = tg.create_task(
                self._fetch_tools(agent_key, since, now),
            )
            delegation_task = tg.create_task(
                self._fetch_delegations(agent_key, since, now),
            )

        cost_records = cost_task.result()
        tool_invocations = tool_task.result()
        sent, received = delegation_task.result()

        timeline = merge_activity_timeline(
            lifecycle_events=lifecycle_events,
            task_metrics=task_metrics,
            cost_records=cost_records,
            tool_invocations=tool_invocations,
            delegation_records_sent=sent,
            delegation_records_received=received,
            currency=DEFAULT_CURRENCY,
        )
        total = len(timeline)
        page = timeline[offset : offset + limit]
        logger.info(
            HR_ACTIVITY_AGENT_FETCHED,
            agent_id=agent_key,
            event_count=len(page),
            total=total,
            window_hours=window_hours,
        )
        return page, total

    async def _fetch_costs(
        self,
        agent_id: str,
        since: datetime,
        now: datetime,
    ) -> tuple:  # type: ignore[type-arg]
        """Best-effort cost record fetch; empty on any failure.

        Wraps the underlying tracker call so a single failing source
        cannot cancel the sibling fetches running in the same
        ``TaskGroup`` (CLAUDE.md async convention for independent
        best-effort workers).
        """
        if self._cost_tracker is None:
            return ()
        try:
            return await self._cost_tracker.get_records(
                agent_id=agent_id,
                start=since,
                end=now,
            )
        except MemoryError, RecursionError:
            raise
        except Exception:
            return ()

    async def _fetch_tools(
        self,
        agent_id: str,
        since: datetime,
        now: datetime,
    ) -> tuple:  # type: ignore[type-arg]
        """Best-effort tool invocation fetch; empty on any failure.

        Same resilience pattern as :meth:`_fetch_costs`: a single
        tracker failure must not abort the whole activity merge.
        """
        if self._tool_invocation_tracker is None:
            return ()
        try:
            return await self._tool_invocation_tracker.get_records(
                agent_id=agent_id,
                start=since,
                end=now,
            )
        except MemoryError, RecursionError:
            raise
        except Exception:
            return ()

    async def _fetch_delegations(
        self,
        agent_id: str,
        since: datetime,
        now: datetime,
    ) -> tuple:  # type: ignore[type-arg]
        """Best-effort delegation fetch; returns ``(sent, received)``.

        Both fetches are independent best-effort workers -- neither
        direction's failure should abort the sibling. Wraps each task
        body per the CLAUDE.md async convention.
        """
        if self._delegation_store is None:
            return (), ()

        async def _safe_delegator() -> tuple:  # type: ignore[type-arg]
            assert self._delegation_store is not None  # noqa: S101
            try:
                return await self._delegation_store.get_records_as_delegator(
                    agent_id,
                    start=since,
                    end=now,
                )
            except MemoryError, RecursionError:
                raise
            except Exception:
                return ()

        async def _safe_delegatee() -> tuple:  # type: ignore[type-arg]
            assert self._delegation_store is not None  # noqa: S101
            try:
                return await self._delegation_store.get_records_as_delegatee(
                    agent_id,
                    start=since,
                    end=now,
                )
            except MemoryError, RecursionError:
                raise
            except Exception:
                return ()

        async with asyncio.TaskGroup() as tg:
            sent_task = tg.create_task(_safe_delegator())
            recv_task = tg.create_task(_safe_delegatee())
        return sent_task.result(), recv_task.result()


__all__ = ["ActivityFeedService"]
