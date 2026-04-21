"""Conformance tests for ``DecisionRepository`` (SQLite + Postgres)."""

from datetime import UTC, datetime

import pytest

from synthorg.core.enums import DecisionOutcome, TaskType
from synthorg.core.task import Task
from synthorg.core.types import NotBlankStr
from synthorg.persistence.protocol import PersistenceBackend

pytestmark = pytest.mark.integration

_NOW = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)


async def _seed_task(backend: PersistenceBackend, task_id: str) -> None:
    """Satisfy the ``decision_records.task_id`` FK by persisting a minimal task row."""
    await backend.tasks.save(
        Task(
            id=NotBlankStr(task_id),
            title=NotBlankStr(task_id),
            description=NotBlankStr("fixture task"),
            type=TaskType.DEVELOPMENT,
            project=NotBlankStr("proj-conf"),
            created_by=NotBlankStr("system"),
        ),
    )


class TestDecisionRepository:
    async def test_append_and_get(self, backend: PersistenceBackend) -> None:
        await _seed_task(backend, "task-001")
        record = await backend.decision_records.append_with_next_version(
            record_id=NotBlankStr("dec-001"),
            task_id=NotBlankStr("task-001"),
            approval_id=NotBlankStr("appr-001"),
            executing_agent_id=NotBlankStr("agent-exec"),
            reviewer_agent_id=NotBlankStr("agent-rev"),
            decision=DecisionOutcome.APPROVED,
            reason="on-spec",
            criteria_snapshot=(NotBlankStr("tests-pass"),),
            recorded_at=_NOW,
        )
        assert record.version == 1

        fetched = await backend.decision_records.get(NotBlankStr("dec-001"))
        assert fetched is not None
        assert fetched.decision == DecisionOutcome.APPROVED
        assert fetched.task_id == "task-001"

    async def test_append_assigns_next_version_per_task(
        self, backend: PersistenceBackend
    ) -> None:
        await _seed_task(backend, "same-task")
        first = await backend.decision_records.append_with_next_version(
            record_id=NotBlankStr("d1"),
            task_id=NotBlankStr("same-task"),
            approval_id=None,
            executing_agent_id=NotBlankStr("a"),
            reviewer_agent_id=NotBlankStr("b"),
            decision=DecisionOutcome.APPROVED,
            reason=None,
            criteria_snapshot=(),
            recorded_at=_NOW,
        )
        second = await backend.decision_records.append_with_next_version(
            record_id=NotBlankStr("d2"),
            task_id=NotBlankStr("same-task"),
            approval_id=None,
            executing_agent_id=NotBlankStr("a"),
            reviewer_agent_id=NotBlankStr("b"),
            decision=DecisionOutcome.REJECTED,
            reason="drift",
            criteria_snapshot=(),
            recorded_at=_NOW,
        )
        assert first.version == 1
        assert second.version == 2

    async def test_get_missing_returns_none(self, backend: PersistenceBackend) -> None:
        assert await backend.decision_records.get(NotBlankStr("ghost")) is None

    async def test_list_by_task(self, backend: PersistenceBackend) -> None:
        await _seed_task(backend, "t")
        await backend.decision_records.append_with_next_version(
            record_id=NotBlankStr("a"),
            task_id=NotBlankStr("t"),
            approval_id=None,
            executing_agent_id=NotBlankStr("exec"),
            reviewer_agent_id=NotBlankStr("rev"),
            decision=DecisionOutcome.APPROVED,
            reason=None,
            criteria_snapshot=(),
            recorded_at=_NOW,
        )
        await backend.decision_records.append_with_next_version(
            record_id=NotBlankStr("b"),
            task_id=NotBlankStr("t"),
            approval_id=None,
            executing_agent_id=NotBlankStr("exec"),
            reviewer_agent_id=NotBlankStr("rev"),
            decision=DecisionOutcome.REJECTED,
            reason="nope",
            criteria_snapshot=(),
            recorded_at=_NOW,
        )

        records = await backend.decision_records.list_by_task(NotBlankStr("t"))
        versions = [r.version for r in records]
        assert versions == [1, 2]

    async def test_list_by_agent_executor_role(
        self, backend: PersistenceBackend
    ) -> None:
        await _seed_task(backend, "tA")
        await backend.decision_records.append_with_next_version(
            record_id=NotBlankStr("e1"),
            task_id=NotBlankStr("tA"),
            approval_id=None,
            executing_agent_id=NotBlankStr("alice"),
            reviewer_agent_id=NotBlankStr("bob"),
            decision=DecisionOutcome.APPROVED,
            reason=None,
            criteria_snapshot=(),
            recorded_at=_NOW,
        )

        as_exec = await backend.decision_records.list_by_agent(
            NotBlankStr("alice"),
            role="executor",
        )
        as_rev = await backend.decision_records.list_by_agent(
            NotBlankStr("alice"),
            role="reviewer",
        )
        # Positive assertion: bob is recorded as the reviewer on the same
        # row, so the reviewer-role path must return exactly one match.
        # Without this the test only proved empty-results path; a broken
        # role filter that silently returned zero for both roles would
        # also pass.
        bob_as_rev = await backend.decision_records.list_by_agent(
            NotBlankStr("bob"),
            role="reviewer",
        )
        assert len(as_exec) == 1
        assert len(as_rev) == 0
        assert len(bob_as_rev) == 1
