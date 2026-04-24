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


class _NoopSelector:
    """Minimal selector protocol stub -- never invoked in session tests."""

    async def select_sources(self, plan: TrainingPlan) -> tuple:  # type: ignore[type-arg]
        return ()


class _NoopCuration:
    """Minimal curation protocol stub -- never invoked in session tests."""

    async def curate(  # type: ignore[no-untyped-def]
        self, items, plan, content_type
    ):
        return ()


class _NoopMemoryBackend:
    """Minimal memory backend stub -- never invoked in session tests."""

    async def store(self, request):  # type: ignore[no-untyped-def]
        return None


def _build_service(*, raises: Exception | None = None) -> TrainingService:
    """Construct a real :class:`TrainingService` wired to noop stubs.

    The session-method tests exercise only ``start_session`` /
    ``list_sessions`` / ``get_session``, which delegate pipeline work
    to ``_execute_locked``. Constructing the full service (rather than
    a subclass that bypasses ``__init__``) ensures that when
    ``TrainingService.__init__`` gains new required state, these tests
    fail with a clear ``TypeError`` instead of silently missing the
    new attribute.

    The returned service has ``_execute_locked`` monkey-patched onto
    the instance so ``start_session`` sees a predictable synthetic
    result (or the requested exception).
    """
    service = TrainingService(
        selector=_NoopSelector(),  # type: ignore[arg-type]
        extractors={},
        curation=_NoopCuration(),  # type: ignore[arg-type]
        guards=(),
        memory_backend=_NoopMemoryBackend(),  # type: ignore[arg-type]
    )
    calls: list[str] = []

    async def _fake_execute_locked(
        plan: TrainingPlan,
    ) -> tuple[TrainingResult, bool]:
        calls.append(str(plan.id))
        if raises is not None:
            raise raises
        return _result(str(plan.id), str(plan.new_agent_id)), True

    # Bind to the instance so future ``__init__`` additions don't
    # affect this test surface; the real class method remains
    # available via ``type(service)._execute_locked`` if needed.
    service._execute_locked = _fake_execute_locked  # type: ignore[method-assign]
    service.calls = calls  # type: ignore[attr-defined]
    return service


class TestStartSession:
    """Happy path + failure path."""

    async def test_records_executed_status_on_success(self) -> None:
        service = _build_service()
        plan = _plan("plan-1")

        result = await service.start_session(plan)

        assert result.plan_id == "plan-1"
        session = await service.get_session(NotBlankStr("plan-1"))
        assert session is not None
        assert session.status == TrainingPlanStatus.EXECUTED
        assert session.executed_at is not None

    async def test_records_failed_status_on_exception(self) -> None:
        boom = RuntimeError("pipeline exploded")
        service = _build_service(raises=boom)
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
        service = _build_service()
        for idx in range(3):
            await service.start_session(
                _plan(plan_id=f"plan-{idx}", new_agent_id=f"agent-{idx}"),
            )

        page, total = await service.list_sessions(offset=0, limit=50)

        assert total == 3
        assert [s.id for s in page] == ["plan-2", "plan-1", "plan-0"]

    async def test_paginates(self) -> None:
        service = _build_service()
        for idx in range(5):
            await service.start_session(
                _plan(plan_id=f"plan-{idx}", new_agent_id=f"agent-{idx}"),
            )

        page, total = await service.list_sessions(offset=2, limit=2)

        assert total == 5
        assert [s.id for s in page] == ["plan-2", "plan-1"]

    async def test_empty_returns_zero_total(self) -> None:
        service = _build_service()

        page, total = await service.list_sessions(offset=0, limit=50)

        assert total == 0
        assert page == ()

    async def test_negative_offset_rejects(self) -> None:
        service = _build_service()

        with pytest.raises(ValueError, match="offset"):
            await service.list_sessions(offset=-1, limit=50)

    async def test_non_positive_limit_rejects(self) -> None:
        service = _build_service()

        with pytest.raises(ValueError, match="limit"):
            await service.list_sessions(offset=0, limit=0)


class TestGetSession:
    """Present + missing."""

    async def test_returns_plan_when_present(self) -> None:
        service = _build_service()
        await service.start_session(_plan("plan-1"))

        session = await service.get_session(NotBlankStr("plan-1"))

        assert session is not None
        assert session.id == "plan-1"

    async def test_returns_none_when_missing(self) -> None:
        service = _build_service()

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
            service = _build_service()
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
