"""Unit tests for TaskSource enum and Task.source field."""

import pytest
from pydantic import ValidationError

from synthorg.core.enums import TaskSource, TaskStatus, TaskType
from synthorg.core.task import Task

pytestmark = pytest.mark.unit


class TestTaskSourceEnum:
    """Tests for the TaskSource enum."""

    def test_has_three_members(self) -> None:
        assert len(TaskSource) == 3

    def test_values(self) -> None:
        assert TaskSource.INTERNAL == "internal"
        assert TaskSource.CLIENT == "client"
        assert TaskSource.SIMULATION == "simulation"


class TestTaskSourceField:
    """Tests for the Task.source field."""

    def _make_task(self, **overrides: object) -> Task:
        defaults: dict[str, object] = {
            "id": "task-001",
            "title": "Test task",
            "description": "A test task",
            "type": TaskType.DEVELOPMENT,
            "project": "proj-001",
            "created_by": "manager",
        }
        defaults.update(overrides)
        return Task(**defaults)  # type: ignore[arg-type]

    def test_source_defaults_to_none(self) -> None:
        task = self._make_task()
        assert task.source is None

    def test_source_internal(self) -> None:
        task = self._make_task(source=TaskSource.INTERNAL)
        assert task.source == TaskSource.INTERNAL

    def test_source_client(self) -> None:
        task = self._make_task(source=TaskSource.CLIENT)
        assert task.source == TaskSource.CLIENT

    def test_source_simulation(self) -> None:
        task = self._make_task(source=TaskSource.SIMULATION)
        assert task.source == TaskSource.SIMULATION

    def test_source_preserved_in_transition(self) -> None:
        task = self._make_task(source=TaskSource.CLIENT)
        assigned = task.with_transition(
            TaskStatus.ASSIGNED,
            assigned_to="agent-1",
        )
        assert assigned.source == TaskSource.CLIENT

    def test_invalid_source_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._make_task(source="invalid")
