"""Tests for credential isolation boundary enforcement."""

import pytest
import structlog.testing

from synthorg.core.enums import Complexity, Priority, TaskStatus, TaskType
from synthorg.core.task import Task
from synthorg.engine._validation import validate_task_metadata
from synthorg.engine.errors import ExecutionStateError
from synthorg.observability.events.execution import (
    EXECUTION_CREDENTIAL_ISOLATION_VIOLATION,
)


def _make_task(metadata: dict[str, object]) -> Task:
    """Create a minimal task with the given metadata."""
    return Task(
        id="task-cred-001",
        title="Test task",
        description="Task for credential isolation testing.",
        type=TaskType.DEVELOPMENT,
        priority=Priority.MEDIUM,
        project="proj-001",
        created_by="tester",
        assigned_to="agent-001",
        status=TaskStatus.ASSIGNED,
        estimated_complexity=Complexity.SIMPLE,
        metadata=metadata,
    )


@pytest.mark.unit
class TestCredentialIsolationValidator:
    """validate_task_metadata rejects credential-like keys."""

    def test_rejects_token_key(self) -> None:
        task = _make_task({"api_token": "leaked"})
        with pytest.raises(ExecutionStateError, match="api_token"):
            validate_task_metadata(task, agent_id="a1", task_id="t1")

    def test_rejects_secret_key(self) -> None:
        task = _make_task({"my_secret": "leaked"})
        with pytest.raises(ExecutionStateError, match="my_secret"):
            validate_task_metadata(task, agent_id="a1", task_id="t1")

    def test_rejects_api_key(self) -> None:
        task = _make_task({"API_KEY": "leaked"})
        with pytest.raises(ExecutionStateError, match="API_KEY"):
            validate_task_metadata(task, agent_id="a1", task_id="t1")

    def test_rejects_api_key_with_hyphen(self) -> None:
        task = _make_task({"api-key": "leaked"})
        with pytest.raises(ExecutionStateError, match="api-key"):
            validate_task_metadata(task, agent_id="a1", task_id="t1")

    def test_rejects_password_key(self) -> None:
        task = _make_task({"db_password": "leaked"})
        with pytest.raises(ExecutionStateError, match="db_password"):
            validate_task_metadata(task, agent_id="a1", task_id="t1")

    def test_rejects_bearer_key(self) -> None:
        task = _make_task({"bearer_token": "leaked"})
        with pytest.raises(ExecutionStateError, match="bearer"):
            validate_task_metadata(task, agent_id="a1", task_id="t1")

    def test_accepts_safe_metadata(self) -> None:
        task = _make_task({"priority": "high", "team": "backend"})
        validate_task_metadata(task, agent_id="a1", task_id="t1")

    def test_accepts_empty_metadata(self) -> None:
        task = _make_task({})
        validate_task_metadata(task, agent_id="a1", task_id="t1")

    def test_rejects_multiple_violations(self) -> None:
        task = _make_task({"api_token": "x", "password": "y"})
        with pytest.raises(ExecutionStateError, match="api_token") as exc_info:
            validate_task_metadata(task, agent_id="a1", task_id="t1")
        assert "password" in str(exc_info.value)

    def test_case_insensitive_matching(self) -> None:
        task = _make_task({"SECRET_VALUE": "leaked"})
        with pytest.raises(ExecutionStateError, match="SECRET_VALUE"):
            validate_task_metadata(task, agent_id="a1", task_id="t1")

    def test_logs_violation_event(self) -> None:
        task = _make_task({"api_token": "leaked"})
        with (
            structlog.testing.capture_logs() as logs,
            pytest.raises(ExecutionStateError),
        ):
            validate_task_metadata(task, agent_id="a1", task_id="t1")

        violation_logs = [
            log
            for log in logs
            if log.get("event") == EXECUTION_CREDENTIAL_ISOLATION_VIOLATION
        ]
        assert len(violation_logs) == 1
        assert violation_logs[0]["agent_id"] == "a1"
        assert violation_logs[0]["task_id"] == "t1"
