"""Tests for WorkflowExecutionObserver."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from synthorg.core.enums import TaskStatus
from synthorg.engine.task_engine_models import TaskStateChanged
from synthorg.engine.workflow.execution_observer import (
    WorkflowExecutionObserver,
)


def _make_event(
    task_id: str = "task-001",
    new_status: TaskStatus = TaskStatus.COMPLETED,
) -> TaskStateChanged:
    """Build a minimal TaskStateChanged event."""
    return TaskStateChanged(
        mutation_type="transition",
        request_id="req-test",
        requested_by="test",
        task_id=task_id,
        task=None,
        previous_status=TaskStatus.IN_PROGRESS,
        new_status=new_status,
        version=2,
        reason="test transition",
        timestamp=datetime.now(UTC),
    )


class TestWorkflowExecutionObserver:
    """Tests for the WorkflowExecutionObserver bridge."""

    @pytest.mark.unit
    def test_constructor_wires_service(self) -> None:
        """Observer creates a WorkflowExecutionService with the given deps."""
        definition_repo = MagicMock()
        execution_repo = MagicMock()
        task_engine = MagicMock()

        observer = WorkflowExecutionObserver(
            definition_repo=definition_repo,
            execution_repo=execution_repo,
            task_engine=task_engine,
        )

        service = observer._service
        assert service._definition_repo is definition_repo
        assert service._execution_repo is execution_repo
        assert service._task_engine is task_engine

    @pytest.mark.unit
    async def test_call_delegates_to_service(self) -> None:
        """__call__ forwards the event to service.handle_task_state_changed."""
        observer = WorkflowExecutionObserver(
            definition_repo=MagicMock(),
            execution_repo=MagicMock(),
            task_engine=MagicMock(),
        )

        event = _make_event()
        mock_handle = AsyncMock()
        with patch.object(
            observer._service,
            "handle_task_state_changed",
            mock_handle,
        ):
            await observer(event)

        mock_handle.assert_awaited_once_with(event)

    @pytest.mark.unit
    async def test_call_with_failed_task_delegates(self) -> None:
        """__call__ forwards FAILED task events to the service."""
        observer = WorkflowExecutionObserver(
            definition_repo=MagicMock(),
            execution_repo=MagicMock(),
            task_engine=MagicMock(),
        )

        event = _make_event(new_status=TaskStatus.FAILED)
        mock_handle = AsyncMock()
        with patch.object(
            observer._service,
            "handle_task_state_changed",
            mock_handle,
        ):
            await observer(event)

        mock_handle.assert_awaited_once_with(event)
