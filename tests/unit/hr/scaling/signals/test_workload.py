"""Tests for workload signal source."""

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.engine.assignment.models import AgentWorkload
from synthorg.hr.scaling.signals.workload import WorkloadSignalSource

_AGENT_IDS = (NotBlankStr("a1"), NotBlankStr("a2"), NotBlankStr("a3"))


def _make_workload(agent_id: str, tasks: int) -> AgentWorkload:
    return AgentWorkload(
        agent_id=NotBlankStr(agent_id),
        active_task_count=tasks,
        total_cost=0.0,
    )


@pytest.mark.unit
class TestWorkloadSignalSource:
    """WorkloadSignalSource signal collection."""

    async def test_empty_workloads_returns_zeros(self) -> None:
        source = WorkloadSignalSource(max_concurrent_tasks=3)
        signals = await source.collect(_AGENT_IDS, workloads=())
        by_name = {s.name: s.value for s in signals}
        assert by_name["avg_utilization"] == 0.0
        assert by_name["peak_utilization"] == 0.0
        assert by_name["queue_depth"] == 0.0

    async def test_full_utilization(self) -> None:
        source = WorkloadSignalSource(max_concurrent_tasks=3)
        workloads = (
            _make_workload("a1", 3),
            _make_workload("a2", 3),
        )
        signals = await source.collect(_AGENT_IDS, workloads=workloads)
        by_name = {s.name: s.value for s in signals}
        assert by_name["avg_utilization"] == 1.0
        assert by_name["peak_utilization"] == 1.0

    async def test_partial_utilization(self) -> None:
        source = WorkloadSignalSource(max_concurrent_tasks=4)
        workloads = (
            _make_workload("a1", 2),  # 0.5
            _make_workload("a2", 4),  # 1.0 (capped)
        )
        signals = await source.collect(_AGENT_IDS, workloads=workloads)
        by_name = {s.name: s.value for s in signals}
        assert by_name["avg_utilization"] == 0.75
        assert by_name["peak_utilization"] == 1.0
        assert by_name["queue_depth"] == 6.0

    async def test_queue_depth_sums_tasks(self) -> None:
        source = WorkloadSignalSource(max_concurrent_tasks=3)
        workloads = (
            _make_workload("a1", 1),
            _make_workload("a2", 2),
            _make_workload("a3", 3),
        )
        signals = await source.collect(_AGENT_IDS, workloads=workloads)
        by_name = {s.name: s.value for s in signals}
        assert by_name["queue_depth"] == 6.0

    async def test_source_name(self) -> None:
        source = WorkloadSignalSource()
        assert source.name == "workload"

    async def test_signal_source_field(self) -> None:
        source = WorkloadSignalSource(max_concurrent_tasks=3)
        workloads = (_make_workload("a1", 1),)
        signals = await source.collect(_AGENT_IDS, workloads=workloads)
        assert all(s.source == "workload" for s in signals)
