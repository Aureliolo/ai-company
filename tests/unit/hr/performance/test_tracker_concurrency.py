"""Concurrency regression tests for PerformanceTracker.

The tracker's ``_metrics_lock`` historically only protected
``record_task_metric`` and the inflection cache.
``record_coordination_contributions`` (synchronous) and
``record_collaboration_event`` (async) both mutated shared dicts without
the lock, which is an open defect waiting for an ``await`` to be inserted
into either body. These tests pin the locked invariant.
"""

import asyncio

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.engine.coordination.attribution import AgentContribution
from synthorg.hr.performance.tracker import PerformanceTracker

from .conftest import make_collab_metric, make_task_metric

_AGENT_ID = "agent-conc-001"


def _make_contribution(
    *,
    agent_id: str = _AGENT_ID,
    subtask_id: str = "subtask-001",
    score: float = 1.0,
) -> AgentContribution:
    return AgentContribution(
        agent_id=NotBlankStr(agent_id),
        subtask_id=NotBlankStr(subtask_id),
        contribution_score=score,
    )


@pytest.mark.unit
class TestTrackerConcurrency:
    """Concurrent writes must not lose records."""

    async def test_concurrent_record_coordination_contributions_no_lost_writes(
        self,
    ) -> None:
        tracker = PerformanceTracker()
        n_calls = 50
        contribs_per_call = 2

        async def _record(i: int) -> None:
            batch = tuple(
                _make_contribution(subtask_id=f"st-{i}-{j}")
                for j in range(contribs_per_call)
            )
            await tracker.record_coordination_contributions(batch)

        await asyncio.gather(*(_record(i) for i in range(n_calls)))

        assert len(tracker._contributions[_AGENT_ID]) == n_calls * contribs_per_call

    async def test_concurrent_record_collaboration_event_no_lost_writes(
        self,
    ) -> None:
        tracker = PerformanceTracker()
        n_events = 50

        async def _record(i: int) -> None:
            record = make_collab_metric(
                agent_id=_AGENT_ID,
                handoff_completeness=float(i % 10) / 10.0,
            )
            await tracker.record_collaboration_event(record)

        await asyncio.gather(*(_record(i) for i in range(n_events)))

        assert len(tracker._collab_metrics[_AGENT_ID]) == n_events

    async def test_mixed_workload_record_task_and_coordination_race_free(
        self,
    ) -> None:
        tracker = PerformanceTracker()

        async def _record_task(i: int) -> None:
            await tracker.record_task_metric(
                make_task_metric(
                    agent_id=_AGENT_ID,
                    task_id=f"t-{i}",
                ),
            )

        async def _record_contrib(i: int) -> None:
            await tracker.record_coordination_contributions(
                (_make_contribution(subtask_id=f"sub-{i}"),),
            )

        await asyncio.gather(
            *(_record_task(i) for i in range(30)),
            *(_record_contrib(i) for i in range(30)),
        )

        assert len(tracker._task_metrics[_AGENT_ID]) == 30
        assert len(tracker._contributions[_AGENT_ID]) == 30
