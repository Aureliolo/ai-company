"""Tests for TaskEngine observer mechanism."""

import pytest

from synthorg.core.enums import TaskStatus, TaskType
from synthorg.core.task import Task
from synthorg.engine.task_engine import TaskEngine
from synthorg.engine.task_engine_models import (
    CreateTaskData,
    TaskStateChanged,
    TransitionTaskMutation,
)

# ── Fake persistence ──────────────────────────────────────────────


class FakeTaskRepo:
    """Minimal fake task repository for observer tests."""

    def __init__(self) -> None:
        self._store: dict[str, Task] = {}

    async def save(self, task: Task) -> None:
        self._store[task.id] = task

    async def get(self, task_id: str) -> Task | None:
        return self._store.get(task_id)

    async def list_tasks(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[Task, ...]:
        tasks = list(self._store.values())
        start = offset or 0
        end = start + limit if limit else len(tasks)
        return tuple(tasks[start:end])

    async def delete(self, task_id: str) -> bool:
        return self._store.pop(task_id, None) is not None


class FakePersistence:
    """Wraps FakeTaskRepo to satisfy PersistenceBackend.tasks."""

    def __init__(self) -> None:
        self.tasks = FakeTaskRepo()


# ── Tests ─────────────────────────────────────────────────────────


class TestRegisterObserver:
    """Tests for register_observer and observer notification."""

    @pytest.mark.unit
    async def test_observer_called_on_successful_mutation(self) -> None:
        """Observer receives TaskStateChanged after a create mutation."""
        persistence = FakePersistence()
        engine = TaskEngine(
            persistence=persistence,  # type: ignore[arg-type]
        )
        engine.start()

        received: list[TaskStateChanged] = []

        async def observer(event: TaskStateChanged) -> None:
            received.append(event)

        engine.register_observer(observer)

        try:
            task = await engine.create_task(
                CreateTaskData(
                    title="Test",
                    description="Desc",
                    type=TaskType.DEVELOPMENT,
                    project="proj-1",
                    created_by="test",
                ),
                requested_by="test",
            )
            assert len(received) == 1
            assert received[0].task_id == task.id
            assert received[0].mutation_type == "create"
        finally:
            await engine.stop()

    @pytest.mark.unit
    async def test_observer_error_logged_not_propagated(self) -> None:
        """A failing observer does not prevent the mutation."""
        persistence = FakePersistence()
        engine = TaskEngine(
            persistence=persistence,  # type: ignore[arg-type]
        )
        engine.start()

        async def bad_observer(event: TaskStateChanged) -> None:
            msg = "Observer failed!"
            raise RuntimeError(msg)

        engine.register_observer(bad_observer)

        try:
            # Should succeed despite observer failure
            task = await engine.create_task(
                CreateTaskData(
                    title="Test",
                    description="Desc",
                    type=TaskType.DEVELOPMENT,
                    project="proj-1",
                    created_by="test",
                ),
                requested_by="test",
            )
            assert task is not None
        finally:
            await engine.stop()

    @pytest.mark.unit
    async def test_multiple_observers_all_called(self) -> None:
        """All registered observers are notified."""
        persistence = FakePersistence()
        engine = TaskEngine(
            persistence=persistence,  # type: ignore[arg-type]
        )
        engine.start()

        calls_a: list[TaskStateChanged] = []
        calls_b: list[TaskStateChanged] = []

        async def observer_a(event: TaskStateChanged) -> None:
            calls_a.append(event)

        async def observer_b(event: TaskStateChanged) -> None:
            calls_b.append(event)

        engine.register_observer(observer_a)
        engine.register_observer(observer_b)

        try:
            await engine.create_task(
                CreateTaskData(
                    title="Test",
                    description="Desc",
                    type=TaskType.DEVELOPMENT,
                    project="proj-1",
                    created_by="test",
                ),
                requested_by="test",
            )
            assert len(calls_a) == 1
            assert len(calls_b) == 1
        finally:
            await engine.stop()

    @pytest.mark.unit
    async def test_observer_not_called_on_failed_mutation(self) -> None:
        """Observer is not called when the mutation fails."""
        persistence = FakePersistence()
        engine = TaskEngine(
            persistence=persistence,  # type: ignore[arg-type]
        )
        engine.start()

        received: list[TaskStateChanged] = []

        async def observer(event: TaskStateChanged) -> None:
            received.append(event)

        engine.register_observer(observer)

        try:
            # Transition a nonexistent task -- should fail
            result = await engine.submit(
                TransitionTaskMutation(
                    request_id="req-1",
                    requested_by="test",
                    task_id="nonexistent-task",
                    target_status=TaskStatus.COMPLETED,
                    reason="test",
                ),
            )
            assert not result.success
            assert len(received) == 0
        finally:
            await engine.stop()

    @pytest.mark.unit
    async def test_observer_receives_transition_event(self) -> None:
        """Observer gets correct previous/new status on transition."""
        persistence = FakePersistence()
        engine = TaskEngine(
            persistence=persistence,  # type: ignore[arg-type]
        )
        engine.start()

        received: list[TaskStateChanged] = []

        async def observer(event: TaskStateChanged) -> None:
            received.append(event)

        engine.register_observer(observer)

        try:
            # Create a task
            task = await engine.create_task(
                CreateTaskData(
                    title="Test",
                    description="Desc",
                    type=TaskType.DEVELOPMENT,
                    project="proj-1",
                    created_by="test",
                ),
                requested_by="test",
            )
            # Transition: CREATED -> ASSIGNED (requires assigned_to)
            result = await engine.submit(
                TransitionTaskMutation(
                    request_id="req-2",
                    requested_by="test",
                    task_id=task.id,
                    target_status=TaskStatus.ASSIGNED,
                    reason="assign",
                    overrides={"assigned_to": "agent-1"},
                ),
            )
            assert result.success
            # 2 events: create + transition
            assert len(received) == 2
            transition_event = received[1]
            assert transition_event.mutation_type == "transition"
            assert transition_event.previous_status is TaskStatus.CREATED
            assert transition_event.new_status is TaskStatus.ASSIGNED
        finally:
            await engine.stop()
