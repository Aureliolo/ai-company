"""Unit tests for the training session methods.

Exercises the in-memory session store that :meth:`TrainingService.start_session`
populates. The pipeline itself is mocked via a subclass override of
``execute`` so these tests stay focused on the session bookkeeping
(ordering, pagination, FIFO eviction, terminal state recording).
"""

from datetime import UTC, datetime

import pytest

from synthorg.core.enums import SeniorityLevel
from synthorg.core.types import NotBlankStr
from synthorg.hr.training.models import (
    ContentType,
    TrainingPlan,
    TrainingPlanStatus,
    TrainingResult,
)
from synthorg.hr.training.service import TrainingService

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 4, 24, 12, 0, tzinfo=UTC)


def _plan(plan_id: str = "plan-1", new_agent_id: str = "agent-new") -> TrainingPlan:
    return TrainingPlan(
        id=NotBlankStr(plan_id),
        new_agent_id=NotBlankStr(new_agent_id),
        new_agent_role=NotBlankStr("engineer"),
        new_agent_level=SeniorityLevel.MID,
        enabled_content_types=frozenset({ContentType.PROCEDURAL}),
        created_at=_NOW,
    )


def _result(plan_id: str = "plan-1", new_agent_id: str = "agent-new") -> TrainingResult:
    return TrainingResult(
        plan_id=NotBlankStr(plan_id),
        new_agent_id=NotBlankStr(new_agent_id),
        started_at=_NOW,
        completed_at=_NOW,
    )


class _StubTrainingService(TrainingService):
    """Subclass that skips the full pipeline for session tests.

    Intentionally bypasses ``TrainingService.__init__``: the real
    constructor wires the full training pipeline (selector / curator /
    trainer / validator / graduation gate), none of which these tests
    exercise. We only call ``start_session`` / ``list_sessions`` /
    ``get_session``, which rely exclusively on the three fields
    manually initialised below (``_idempotency_lock``, ``_sessions``,
    ``_session_lock``). If ``TrainingService.__init__`` gains new
    initialisation logic that ``start_session`` depends on, these
    tests will start failing -- that is the intended signal to update
    this stub.
    """

    def __init__(
        self,
        *,
        raises: Exception | None = None,
    ) -> None:
        self._executed_plan_ids = set()
        import asyncio as _asyncio
        from collections import OrderedDict

        self._idempotency_lock = _asyncio.Lock()
        self._sessions = OrderedDict()
        self._session_lock = _asyncio.Lock()
        self._raises = raises
        self.calls: list[str] = []

    async def execute(self, plan: TrainingPlan) -> TrainingResult:
        self.calls.append(str(plan.id))
        if self._raises is not None:
            raise self._raises
        return _result(str(plan.id), str(plan.new_agent_id))


class TestStartSession:
    """Happy path + failure path."""

    async def test_records_executed_status_on_success(self) -> None:
        service = _StubTrainingService()
        plan = _plan("plan-1")

        result = await service.start_session(plan)

        assert result.plan_id == "plan-1"
        session = await service.get_session(NotBlankStr("plan-1"))
        assert session is not None
        assert session.status == TrainingPlanStatus.EXECUTED
        assert session.executed_at is not None

    async def test_records_failed_status_on_exception(self) -> None:
        boom = RuntimeError("pipeline exploded")
        service = _StubTrainingService(raises=boom)
        plan = _plan("plan-2")

        with pytest.raises(RuntimeError, match="pipeline exploded"):
            await service.start_session(plan)

        session = await service.get_session(NotBlankStr("plan-2"))
        assert session is not None
        assert session.status == TrainingPlanStatus.FAILED
        assert session.executed_at is not None


class TestListSessions:
    """Ordering + pagination + FIFO eviction."""

    async def test_newest_first(self) -> None:
        service = _StubTrainingService()
        for idx in range(3):
            await service.start_session(
                _plan(plan_id=f"plan-{idx}", new_agent_id=f"agent-{idx}"),
            )

        page, total = await service.list_sessions(offset=0, limit=50)

        assert total == 3
        assert [s.id for s in page] == ["plan-2", "plan-1", "plan-0"]

    async def test_paginates(self) -> None:
        service = _StubTrainingService()
        for idx in range(5):
            await service.start_session(
                _plan(plan_id=f"plan-{idx}", new_agent_id=f"agent-{idx}"),
            )

        page, total = await service.list_sessions(offset=2, limit=2)

        assert total == 5
        assert [s.id for s in page] == ["plan-2", "plan-1"]

    async def test_empty_returns_zero_total(self) -> None:
        service = _StubTrainingService()

        page, total = await service.list_sessions(offset=0, limit=50)

        assert total == 0
        assert page == ()


class TestGetSession:
    """Present + missing."""

    async def test_returns_plan_when_present(self) -> None:
        service = _StubTrainingService()
        await service.start_session(_plan("plan-1"))

        session = await service.get_session(NotBlankStr("plan-1"))

        assert session is not None
        assert session.id == "plan-1"

    async def test_returns_none_when_missing(self) -> None:
        service = _StubTrainingService()

        session = await service.get_session(NotBlankStr("nope"))

        assert session is None


class TestSessionCap:
    """FIFO eviction beyond the in-memory cap."""

    async def test_oldest_sessions_evicted_beyond_cap(self) -> None:
        from synthorg.hr.training import service as svc_mod

        # Shrink the cap to keep the test fast while still exercising
        # the eviction loop.
        original = svc_mod._SESSION_STORE_MAX
        svc_mod._SESSION_STORE_MAX = 3
        try:
            service = _StubTrainingService()
            for idx in range(5):
                await service.start_session(
                    _plan(
                        plan_id=f"plan-{idx}",
                        new_agent_id=f"agent-{idx}",
                    ),
                )

            page, total = await service.list_sessions(offset=0, limit=10)
        finally:
            svc_mod._SESSION_STORE_MAX = original

        # Older entries dropped; the 3 most recent survive.
        assert total == 3
        assert [s.id for s in page] == ["plan-4", "plan-3", "plan-2"]
