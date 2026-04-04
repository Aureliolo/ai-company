"""Tests for TaskEngine observer mechanism."""

from collections.abc import AsyncGenerator

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
        status: TaskStatus | None = None,
        assigned_to: str | None = None,
        project: str | None = None,
    ) -> tuple[Task, ...]:
        tasks = list(self._store.values())
        if status is not None:
            tasks = [t for t in tasks if t.status is status]
        if assigned_to is not None:
            tasks = [t for t in tasks if t.assigned_to == assigned_to]
        if project is not None:
            tasks = [t for t in tasks if t.project == project]
        return tuple(tasks)

    async def delete(self, task_id: str) -> bool:
        return self._store.pop(task_id, None) is not None


class FakePersistence:
    """Wraps FakeTaskRepo to satisfy PersistenceBackend.tasks."""

    def __init__(self) -> None:
        self.tasks = FakeTaskRepo()


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
async def started_engine() -> AsyncGenerator[TaskEngine]:
    """Yield a started TaskEngine and stop it on teardown."""
    persistence = FakePersistence()
    engine = TaskEngine(
        persistence=persistence,  # type: ignore[arg-type]
    )
    engine.start()
    yield engine
    await engine.stop()


# ── Tests ─────────────────────────────────────────────────────────


class TestRegisterObserver:
    """Tests for register_observer and observer notification."""

    @pytest.mark.unit
    async def test_observer_called_on_successful_mutation(
        self,
        started_engine: TaskEngine,
    ) -> None:
        """Observer receives TaskStateChanged after a create mutation."""
        received: list[TaskStateChanged] = []

        async def observer(event: TaskStateChanged) -> None:
            received.append(event)

        started_engine.register_observer(observer)

        task = await started_engine.create_task(
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

    @pytest.mark.unit
    async def test_observer_error_logged_not_propagated(
        self,
        started_engine: TaskEngine,
    ) -> None:
        """A failing observer does not prevent the mutation."""

        async def bad_observer(event: TaskStateChanged) -> None:
            msg = "Observer failed!"
            raise RuntimeError(msg)

        started_engine.register_observer(bad_observer)

        # Should succeed despite observer failure
        task = await started_engine.create_task(
            CreateTaskData(
                title="Resilient Task",
                description="Survives observer failure",
                type=TaskType.DEVELOPMENT,
                project="proj-1",
                created_by="test",
            ),
            requested_by="test",
        )
        assert task is not None
        assert task.title == "Resilient Task"
        assert task.description == "Survives observer failure"
        assert task.type is TaskType.DEVELOPMENT

    @pytest.mark.unit
    async def test_multiple_observers_all_called(
        self,
        started_engine: TaskEngine,
    ) -> None:
        """All registered observers are notified."""
        calls_a: list[TaskStateChanged] = []
        calls_b: list[TaskStateChanged] = []

        async def observer_a(event: TaskStateChanged) -> None:
            calls_a.append(event)

        async def observer_b(event: TaskStateChanged) -> None:
            calls_b.append(event)

        started_engine.register_observer(observer_a)
        started_engine.register_observer(observer_b)

        await started_engine.create_task(
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

    @pytest.mark.unit
    async def test_observer_not_called_on_failed_mutation(
        self,
        started_engine: TaskEngine,
    ) -> None:
        """Observer is not called when the mutation fails."""
        received: list[TaskStateChanged] = []

        async def observer(event: TaskStateChanged) -> None:
            received.append(event)

        started_engine.register_observer(observer)

        # Transition a nonexistent task -- should fail
        result = await started_engine.submit(
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

    @pytest.mark.unit
    async def test_observer_receives_transition_event(
        self,
        started_engine: TaskEngine,
    ) -> None:
        """Observer gets correct previous/new status on transition."""
        received: list[TaskStateChanged] = []

        async def observer(event: TaskStateChanged) -> None:
            received.append(event)

        started_engine.register_observer(observer)

        # Create a task
        task = await started_engine.create_task(
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
        result = await started_engine.submit(
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
