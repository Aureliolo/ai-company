"""Conformance tests for ``TrainingPlanRepository``."""

from datetime import UTC, datetime, timedelta

import pytest

from synthorg.core.enums import SeniorityLevel
from synthorg.core.types import NotBlankStr
from synthorg.hr.training.models import (
    ContentType,
    TrainingPlan,
    TrainingPlanStatus,
)
from synthorg.persistence.protocol import PersistenceBackend

pytestmark = pytest.mark.integration

_NOW = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)


def _plan(
    *,
    plan_id: str = "plan-001",
    agent_id: str = "agent-new-001",
    status: TrainingPlanStatus = TrainingPlanStatus.PENDING,
    created_at: datetime = _NOW,
    executed_at: datetime | None = None,
) -> TrainingPlan:
    return TrainingPlan(
        id=NotBlankStr(plan_id),
        new_agent_id=NotBlankStr(agent_id),
        new_agent_role=NotBlankStr("engineer"),
        new_agent_level=SeniorityLevel.JUNIOR,
        new_agent_department=NotBlankStr("engineering"),
        enabled_content_types=frozenset(ContentType),
        volume_caps=(
            (ContentType.PROCEDURAL, 50),
            (ContentType.SEMANTIC, 10),
            (ContentType.TOOL_PATTERNS, 20),
        ),
        status=status,
        created_at=created_at,
        executed_at=executed_at,
    )


class TestTrainingPlanRepository:
    async def test_save_and_get(self, backend: PersistenceBackend) -> None:
        await backend.training_plans.save(_plan())

        fetched = await backend.training_plans.get(NotBlankStr("plan-001"))
        assert fetched is not None
        assert fetched.new_agent_id == "agent-new-001"
        assert fetched.status is TrainingPlanStatus.PENDING

    async def test_get_missing_returns_none(self, backend: PersistenceBackend) -> None:
        assert await backend.training_plans.get(NotBlankStr("ghost")) is None

    async def test_save_upsert(self, backend: PersistenceBackend) -> None:
        await backend.training_plans.save(_plan())
        await backend.training_plans.save(
            _plan(
                status=TrainingPlanStatus.EXECUTED,
                executed_at=_NOW + timedelta(hours=1),
            ),
        )

        fetched = await backend.training_plans.get(NotBlankStr("plan-001"))
        assert fetched is not None
        assert fetched.status is TrainingPlanStatus.EXECUTED

    async def test_latest_pending_returns_newest(
        self, backend: PersistenceBackend
    ) -> None:
        await backend.training_plans.save(
            _plan(plan_id="p-old", created_at=_NOW - timedelta(hours=2)),
        )
        await backend.training_plans.save(
            _plan(plan_id="p-new", created_at=_NOW),
        )
        await backend.training_plans.save(
            _plan(
                plan_id="p-executed",
                status=TrainingPlanStatus.EXECUTED,
                executed_at=_NOW + timedelta(hours=1),
                created_at=_NOW + timedelta(minutes=30),
            ),
        )

        latest = await backend.training_plans.latest_pending(
            NotBlankStr("agent-new-001"),
        )
        assert latest is not None
        assert latest.id == "p-new"

    async def test_latest_pending_none(self, backend: PersistenceBackend) -> None:
        assert await backend.training_plans.latest_pending(NotBlankStr("ghost")) is None

    async def test_latest_by_agent_ignores_status(
        self, backend: PersistenceBackend
    ) -> None:
        await backend.training_plans.save(_plan(plan_id="p1", created_at=_NOW))
        await backend.training_plans.save(
            _plan(
                plan_id="p2",
                status=TrainingPlanStatus.EXECUTED,
                created_at=_NOW + timedelta(minutes=5),
                executed_at=_NOW + timedelta(minutes=10),
            ),
        )

        latest = await backend.training_plans.latest_by_agent(
            NotBlankStr("agent-new-001"),
        )
        assert latest is not None
        assert latest.id == "p2"

    async def test_list_by_agent_descending(self, backend: PersistenceBackend) -> None:
        await backend.training_plans.save(_plan(plan_id="older", created_at=_NOW))
        await backend.training_plans.save(
            _plan(plan_id="newer", created_at=_NOW + timedelta(minutes=1)),
        )

        rows = await backend.training_plans.list_by_agent(
            NotBlankStr("agent-new-001"),
        )
        ids = [r.id for r in rows]
        assert ids == ["newer", "older"]
