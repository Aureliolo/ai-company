"""Tests for async task protocol models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from synthorg.communication.async_tasks.models import (
    AsyncTaskRecord,
    AsyncTaskStateChannel,
    AsyncTaskStatus,
    TaskSpec,
)


def _make_record(**overrides: object) -> AsyncTaskRecord:
    defaults: dict[str, object] = {
        "task_id": "task-1",
        "agent_name": "researcher",
        "status": AsyncTaskStatus.RUNNING,
        "created_at": datetime(2026, 4, 14, tzinfo=UTC),
        "updated_at": datetime(2026, 4, 14, tzinfo=UTC),
    }
    defaults.update(overrides)
    return AsyncTaskRecord(**defaults)  # type: ignore[arg-type]


@pytest.mark.unit
class TestAsyncTaskStatus:
    def test_all_values(self) -> None:
        values = {s.value for s in AsyncTaskStatus}
        assert values == {
            "pending",
            "running",
            "completed",
            "failed",
            "cancelled",
        }


@pytest.mark.unit
class TestAsyncTaskRecord:
    def test_minimal_valid(self) -> None:
        r = _make_record()
        assert r.task_id == "task-1"
        assert r.agent_name == "researcher"
        assert r.status == AsyncTaskStatus.RUNNING
        assert r.subtask_id is None

    def test_with_subtask_id(self) -> None:
        r = _make_record(subtask_id="sub-1")
        assert r.subtask_id == "sub-1"

    def test_frozen(self) -> None:
        r = _make_record()
        with pytest.raises(ValidationError):
            r.status = AsyncTaskStatus.COMPLETED  # type: ignore[misc]

    def test_blank_task_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_record(task_id="")

    def test_blank_agent_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_record(agent_name="")


@pytest.mark.unit
class TestTaskSpec:
    def test_minimal_valid(self) -> None:
        spec = TaskSpec(
            title="Research topic",
            description="Find information about X",
            agent_id="researcher-1",
        )
        assert spec.title == "Research topic"
        assert spec.parent_task_id is None
        assert spec.metadata == {}

    def test_with_parent_and_metadata(self) -> None:
        spec = TaskSpec(
            title="Sub-research",
            description="Dig deeper",
            agent_id="researcher-2",
            parent_task_id="parent-1",
            metadata={"priority": "high"},
        )
        assert spec.parent_task_id == "parent-1"
        assert spec.metadata == {"priority": "high"}

    def test_frozen(self) -> None:
        spec = TaskSpec(
            title="Task",
            description="Desc",
            agent_id="ag-1",
        )
        with pytest.raises(ValidationError):
            spec.title = "New"  # type: ignore[misc]


@pytest.mark.unit
class TestAsyncTaskStateChannel:
    def test_empty_channel(self) -> None:
        ch = AsyncTaskStateChannel()
        assert ch.records == ()
        assert ch.get("nonexistent") is None

    def test_with_record_adds(self) -> None:
        ch = AsyncTaskStateChannel()
        r = _make_record()
        ch2 = ch.with_record(r)
        assert len(ch2.records) == 1
        assert ch2.records[0].task_id == "task-1"
        # Original unchanged
        assert len(ch.records) == 0

    def test_with_record_replaces_same_task_id(self) -> None:
        r1 = _make_record(status=AsyncTaskStatus.RUNNING)
        r2 = _make_record(status=AsyncTaskStatus.COMPLETED)
        ch = AsyncTaskStateChannel().with_record(r1).with_record(r2)
        assert len(ch.records) == 1
        assert ch.records[0].status == AsyncTaskStatus.COMPLETED

    def test_with_record_multiple_tasks(self) -> None:
        r1 = _make_record(task_id="task-1")
        r2 = _make_record(task_id="task-2", agent_name="writer")
        ch = AsyncTaskStateChannel().with_record(r1).with_record(r2)
        assert len(ch.records) == 2

    def test_with_updated_changes_status(self) -> None:
        r = _make_record(status=AsyncTaskStatus.RUNNING)
        ch = AsyncTaskStateChannel().with_record(r)
        now = datetime(2026, 4, 14, 1, 0, tzinfo=UTC)
        ch2 = ch.with_updated("task-1", AsyncTaskStatus.COMPLETED, now)
        assert ch2.records[0].status == AsyncTaskStatus.COMPLETED
        assert ch2.records[0].updated_at == now

    def test_with_updated_unknown_task_returns_unchanged(self) -> None:
        ch = AsyncTaskStateChannel()
        now = datetime(2026, 4, 14, tzinfo=UTC)
        ch2 = ch.with_updated("nonexistent", AsyncTaskStatus.FAILED, now)
        assert ch2.records == ()

    def test_get_existing(self) -> None:
        r = _make_record()
        ch = AsyncTaskStateChannel().with_record(r)
        found = ch.get("task-1")
        assert found is not None
        assert found.task_id == "task-1"

    def test_get_not_found(self) -> None:
        ch = AsyncTaskStateChannel().with_record(_make_record())
        assert ch.get("other") is None

    def test_frozen(self) -> None:
        ch = AsyncTaskStateChannel()
        with pytest.raises(ValidationError):
            ch.records = ()  # type: ignore[misc]
