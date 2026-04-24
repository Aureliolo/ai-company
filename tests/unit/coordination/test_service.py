"""Unit tests for :class:`CoordinationService`."""

from datetime import UTC, datetime

import pytest

from synthorg.budget.coordination_store import (
    CoordinationMetricsRecord,
    CoordinationMetricsStore,
)
from synthorg.coordination.service import CoordinationService
from synthorg.core.types import NotBlankStr

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 4, 24, 12, 0, tzinfo=UTC)


def _record(
    task_id: str = "task-1",
    *,
    offset_seconds: int = 0,
    team_size: int = 3,
) -> CoordinationMetricsRecord:
    # Build a minimal ``CoordinationMetrics`` proxy -- the nine-metric
    # rollup exposes many fields; we use the real dataclass so the
    # frozen model accepts it. ``model_construct`` side-steps
    # constructor validators since we only need the record to match
    # the store's serialization contract.
    from synthorg.budget.coordination_metrics import CoordinationMetrics

    metrics = CoordinationMetrics.model_construct()
    return CoordinationMetricsRecord(
        task_id=NotBlankStr(task_id),
        agent_id=NotBlankStr("agent-lead"),
        computed_at=_NOW,
        team_size=team_size,
        metrics=metrics,
    )


class TestCoordinateTask:
    """Lookup by task_id."""

    async def test_returns_newest_record(self) -> None:
        store = CoordinationMetricsStore()
        store.record(_record("task-1"))
        store.record(_record("task-1", team_size=5))
        service = CoordinationService(metrics_store=store)

        result = await service.coordinate_task(NotBlankStr("task-1"))

        assert result is not None
        assert result.team_size == 5

    async def test_returns_none_for_unknown_task(self) -> None:
        store = CoordinationMetricsStore()
        service = CoordinationService(metrics_store=store)

        result = await service.coordinate_task(NotBlankStr("missing"))

        assert result is None


class TestListMetrics:
    """Pagination + total."""

    async def test_paginates_with_total(self) -> None:
        store = CoordinationMetricsStore()
        for idx in range(5):
            store.record(_record(f"task-{idx}"))
        service = CoordinationService(metrics_store=store)

        page, total = await service.list_metrics(offset=1, limit=2)

        assert total == 5
        assert len(page) == 2

    async def test_empty_returns_zero_total(self) -> None:
        service = CoordinationService(
            metrics_store=CoordinationMetricsStore(),
        )

        page, total = await service.list_metrics(offset=0, limit=50)

        assert total == 0
        assert page == ()

    async def test_offset_past_end_returns_empty(self) -> None:
        store = CoordinationMetricsStore()
        store.record(_record("task-1"))
        service = CoordinationService(metrics_store=store)

        page, total = await service.list_metrics(offset=10, limit=50)

        assert total == 1
        assert page == ()
