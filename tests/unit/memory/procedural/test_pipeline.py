"""Tests for the procedural memory pipeline (end-to-end)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import structlog.testing

from synthorg.core.enums import MemoryCategory, TaskStatus, TaskType
from synthorg.core.task import Task
from synthorg.engine.context import AgentContext, AgentContextSnapshot
from synthorg.engine.loop_protocol import ExecutionResult, TerminationReason, TurnRecord
from synthorg.engine.recovery import RecoveryResult
from synthorg.engine.task_execution import TaskExecution
from synthorg.memory.models import MemoryStoreRequest
from synthorg.memory.procedural.models import ProceduralMemoryProposal
from synthorg.memory.procedural.pipeline import (
    _build_payload,
    _format_procedural_content,
    propose_procedural_memory,
)
from synthorg.observability.events.procedural_memory import (
    PROCEDURAL_MEMORY_SKIPPED,
    PROCEDURAL_MEMORY_START,
    PROCEDURAL_MEMORY_STORE_FAILED,
    PROCEDURAL_MEMORY_STORED,
)
from synthorg.providers.enums import FinishReason
from synthorg.providers.models import TokenUsage


def _make_task(**overrides: object) -> Task:
    defaults: dict[str, object] = {
        "id": "task-pipe-001",
        "title": "Implement caching layer",
        "description": "Add Redis caching to the API.",
        "type": TaskType.DEVELOPMENT,
        "project": "proj-001",
        "created_by": "product_manager",
        "assigned_to": "agent-001",
        "status": TaskStatus.ASSIGNED,
    }
    defaults.update(overrides)
    return Task(**defaults)


def _make_recovery_result(
    *,
    task: Task | None = None,
    error_message: str = "Provider timeout",
) -> RecoveryResult:
    t = task or _make_task()
    agent_id = str(uuid4())
    exec_id = str(uuid4())
    te = TaskExecution.from_task(t)
    te = te.with_transition(TaskStatus.IN_PROGRESS, reason="started")
    te = te.with_transition(TaskStatus.FAILED, reason=error_message)
    snapshot = AgentContextSnapshot(
        execution_id=exec_id,
        agent_id=agent_id,
        task_id=t.id,
        turn_count=3,
        accumulated_cost=TokenUsage(
            input_tokens=500,
            output_tokens=200,
            cost_usd=0.01,
        ),
        task_status=TaskStatus.FAILED,
        started_at=datetime.now(UTC),
        snapshot_at=datetime.now(UTC),
        message_count=6,
    )
    return RecoveryResult(
        task_execution=te,
        strategy_type="fail_reassign",
        context_snapshot=snapshot,
        error_message=error_message,
    )


def _make_execution_result(
    *,
    turn_tool_calls: tuple[tuple[str, ...], ...] = (
        ("code_search",),
        ("run_tests", "write_file"),
    ),
) -> ExecutionResult:
    turns = tuple(
        TurnRecord(
            turn_number=i + 1,
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.001,
            tool_calls_made=tools,
            finish_reason=FinishReason.STOP,
        )
        for i, tools in enumerate(turn_tool_calls)
    )
    task = _make_task()
    ctx = AgentContext.from_identity(_make_identity(), task=task)
    ctx = ctx.with_task_transition(TaskStatus.IN_PROGRESS, reason="started")
    return ExecutionResult(
        context=ctx,
        termination_reason=TerminationReason.ERROR,
        turns=turns,
        error_message="Provider timeout",
    )


def _make_identity():
    from datetime import date

    from synthorg.core.agent import AgentIdentity, ModelConfig

    return AgentIdentity(
        id=uuid4(),
        name="Test Agent",
        role="Developer",
        department="Engineering",
        model=ModelConfig(provider="test-provider", model_id="test-model-001"),
        hiring_date=date(2026, 1, 1),
    )


def _make_proposal(**overrides: object) -> ProceduralMemoryProposal:
    defaults: dict[str, object] = {
        "discovery": "Break large tasks into subtasks when facing timeouts.",
        "condition": "Task fails due to provider timeout after multiple turns.",
        "action": "Decompose the task before retrying.",
        "rationale": "Smaller tasks use less context and are less likely to timeout.",
        "confidence": 0.85,
        "tags": ("timeout", "decomposition"),
    }
    defaults.update(overrides)
    return ProceduralMemoryProposal(**defaults)


# -- _build_payload ---------------------------------------------------


@pytest.mark.unit
class TestBuildPayload:
    def test_extracts_task_fields(self) -> None:
        recovery = _make_recovery_result()
        execution = _make_execution_result()

        payload = _build_payload(execution, recovery)

        assert payload.task_id == "task-pipe-001"
        assert payload.task_title == "Implement caching layer"
        assert payload.task_description == "Add Redis caching to the API."
        assert payload.task_type is TaskType.DEVELOPMENT

    def test_extracts_error_and_strategy(self) -> None:
        recovery = _make_recovery_result(error_message="Budget exhausted")
        execution = _make_execution_result()

        payload = _build_payload(execution, recovery)

        assert payload.error_message == "Budget exhausted"
        assert payload.strategy_type == "fail_reassign"
        assert payload.termination_reason == "error"

    def test_flattens_tool_calls_from_turns(self) -> None:
        execution = _make_execution_result(
            turn_tool_calls=(
                ("code_search",),
                ("run_tests", "write_file"),
                ("code_search",),
            ),
        )
        recovery = _make_recovery_result()

        payload = _build_payload(execution, recovery)

        assert payload.tool_calls_made == (
            "code_search",
            "run_tests",
            "write_file",
            "code_search",
        )

    def test_empty_turns_yields_empty_tool_calls(self) -> None:
        execution = _make_execution_result(turn_tool_calls=())
        recovery = _make_recovery_result()

        payload = _build_payload(execution, recovery)
        assert payload.tool_calls_made == ()

    def test_retry_fields(self) -> None:
        recovery = _make_recovery_result()
        execution = _make_execution_result()

        payload = _build_payload(execution, recovery)
        assert payload.retry_count == recovery.task_execution.retry_count
        assert payload.max_retries == recovery.task_execution.task.max_retries
        assert payload.can_reassign == recovery.can_reassign


# -- _format_procedural_content ----------------------------------------


@pytest.mark.unit
class TestFormatProceduralContent:
    def test_three_tier_structure(self) -> None:
        proposal = _make_proposal()
        content = _format_procedural_content(proposal)

        assert "[DISCOVERY]" in content
        assert "[CONDITION]" in content
        assert "[ACTION]" in content
        assert "[RATIONALE]" in content

    def test_contains_proposal_text(self) -> None:
        proposal = _make_proposal(discovery="Use smaller context windows.")
        content = _format_procedural_content(proposal)

        assert "Use smaller context windows." in content


# -- propose_procedural_memory -----------------------------------------


@pytest.mark.unit
class TestProposeProcedualMemory:
    async def test_happy_path_stores_and_returns_id(self) -> None:
        proposer = AsyncMock()
        proposer.propose = AsyncMock(return_value=_make_proposal())
        backend = AsyncMock()
        backend.store = AsyncMock(return_value="mem-001")

        execution = _make_execution_result()
        recovery = _make_recovery_result()

        with structlog.testing.capture_logs() as logs:
            result = await propose_procedural_memory(
                execution,
                recovery,
                agent_id="agent-001",
                task_id="task-pipe-001",
                proposer=proposer,
                memory_backend=backend,
            )

        assert result == "mem-001"
        backend.store.assert_awaited_once()
        store_call = backend.store.call_args
        assert store_call[0][0] == "agent-001"
        request: MemoryStoreRequest = store_call[0][1]
        assert request.category is MemoryCategory.PROCEDURAL
        assert "non-inferable" in request.metadata.tags
        assert request.metadata.source == "failure:task-pipe-001"

        events = [entry["event"] for entry in logs]
        assert PROCEDURAL_MEMORY_START in events
        assert PROCEDURAL_MEMORY_STORED in events

    async def test_proposer_returns_none_skips_store(self) -> None:
        proposer = AsyncMock()
        proposer.propose = AsyncMock(return_value=None)
        backend = AsyncMock()

        execution = _make_execution_result()
        recovery = _make_recovery_result()

        with structlog.testing.capture_logs() as logs:
            result = await propose_procedural_memory(
                execution,
                recovery,
                agent_id="agent-001",
                task_id="task-pipe-001",
                proposer=proposer,
                memory_backend=backend,
            )

        assert result is None
        backend.store.assert_not_awaited()
        events = [entry["event"] for entry in logs]
        assert PROCEDURAL_MEMORY_SKIPPED in events

    async def test_store_failure_returns_none(self) -> None:
        proposer = AsyncMock()
        proposer.propose = AsyncMock(return_value=_make_proposal())
        backend = AsyncMock()
        backend.store = AsyncMock(side_effect=RuntimeError("store failed"))

        execution = _make_execution_result()
        recovery = _make_recovery_result()

        with structlog.testing.capture_logs() as logs:
            result = await propose_procedural_memory(
                execution,
                recovery,
                agent_id="agent-001",
                task_id="task-pipe-001",
                proposer=proposer,
                memory_backend=backend,
            )

        assert result is None
        events = [entry["event"] for entry in logs]
        assert PROCEDURAL_MEMORY_STORE_FAILED in events

    async def test_tags_include_proposal_tags(self) -> None:
        proposer = AsyncMock()
        proposer.propose = AsyncMock(
            return_value=_make_proposal(tags=("api_error", "retry")),
        )
        backend = AsyncMock()
        backend.store = AsyncMock(return_value="mem-002")

        execution = _make_execution_result()
        recovery = _make_recovery_result()

        await propose_procedural_memory(
            execution,
            recovery,
            agent_id="agent-001",
            task_id="task-pipe-001",
            proposer=proposer,
            memory_backend=backend,
        )

        request: MemoryStoreRequest = backend.store.call_args[0][1]
        assert "non-inferable" in request.metadata.tags
        assert "api_error" in request.metadata.tags
        assert "retry" in request.metadata.tags

    async def test_confidence_passed_to_metadata(self) -> None:
        proposer = AsyncMock()
        proposer.propose = AsyncMock(
            return_value=_make_proposal(confidence=0.72),
        )
        backend = AsyncMock()
        backend.store = AsyncMock(return_value="mem-003")

        execution = _make_execution_result()
        recovery = _make_recovery_result()

        await propose_procedural_memory(
            execution,
            recovery,
            agent_id="agent-001",
            task_id="task-pipe-001",
            proposer=proposer,
            memory_backend=backend,
        )

        request: MemoryStoreRequest = backend.store.call_args[0][1]
        assert request.metadata.confidence == 0.72
