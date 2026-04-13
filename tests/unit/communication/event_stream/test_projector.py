"""Tests for the event projector."""

import pytest

from synthorg.communication.event_stream.projector import (
    PROJECTION_MAP,
    project_event,
)
from synthorg.communication.event_stream.types import AgUiEventType
from synthorg.observability.events.approval_gate import (
    APPROVAL_GATE_CONTEXT_PARKED,
    APPROVAL_GATE_CONTEXT_RESUMED,
)
from synthorg.observability.events.conflict import CONFLICT_DISSENT_RECORDED
from synthorg.observability.events.execution import (
    EXECUTION_ENGINE_COMPLETE,
    EXECUTION_ENGINE_ERROR,
    EXECUTION_ENGINE_START,
    EXECUTION_LOOP_TOOL_CALLS,
    EXECUTION_LOOP_TURN_COMPLETE,
    EXECUTION_LOOP_TURN_START,
    EXECUTION_PLAN_STEP_COMPLETE,
    EXECUTION_PLAN_STEP_FAILED,
    EXECUTION_PLAN_STEP_START,
)


@pytest.mark.unit
class TestProjectionMap:
    def test_engine_start(self) -> None:
        expected = AgUiEventType.RUN_STARTED
        assert PROJECTION_MAP[EXECUTION_ENGINE_START] == expected

    def test_engine_complete(self) -> None:
        expected = AgUiEventType.RUN_FINISHED
        assert PROJECTION_MAP[EXECUTION_ENGINE_COMPLETE] == expected

    def test_engine_error(self) -> None:
        expected = AgUiEventType.RUN_ERROR
        assert PROJECTION_MAP[EXECUTION_ENGINE_ERROR] == expected

    def test_step_start(self) -> None:
        expected = AgUiEventType.STEP_STARTED
        assert PROJECTION_MAP[EXECUTION_PLAN_STEP_START] == expected

    def test_step_complete(self) -> None:
        expected = AgUiEventType.STEP_FINISHED
        assert PROJECTION_MAP[EXECUTION_PLAN_STEP_COMPLETE] == expected

    def test_step_failed(self) -> None:
        expected = AgUiEventType.STEP_FAILED
        assert PROJECTION_MAP[EXECUTION_PLAN_STEP_FAILED] == expected

    def test_turn_start(self) -> None:
        expected = AgUiEventType.TEXT_MESSAGE_START
        assert PROJECTION_MAP[EXECUTION_LOOP_TURN_START] == expected

    def test_turn_complete(self) -> None:
        expected = AgUiEventType.TEXT_MESSAGE_END
        assert PROJECTION_MAP[EXECUTION_LOOP_TURN_COMPLETE] == expected

    def test_tool_calls(self) -> None:
        expected = AgUiEventType.TOOL_CALL_START
        assert PROJECTION_MAP[EXECUTION_LOOP_TOOL_CALLS] == expected

    def test_approval_parked(self) -> None:
        expected = AgUiEventType.APPROVAL_INTERRUPT
        assert PROJECTION_MAP[APPROVAL_GATE_CONTEXT_PARKED] == expected

    def test_approval_resumed(self) -> None:
        expected = AgUiEventType.APPROVAL_RESUMED
        assert PROJECTION_MAP[APPROVAL_GATE_CONTEXT_RESUMED] == expected

    def test_dissent(self) -> None:
        expected = AgUiEventType.DISSENT
        assert PROJECTION_MAP[CONFLICT_DISSENT_RECORDED] == expected


@pytest.mark.unit
class TestProjectEvent:
    def test_mapped_event_returns_stream_event(self) -> None:
        result = project_event(
            EXECUTION_ENGINE_START,
            session_id="s1",
        )
        assert result is not None
        assert result.type == AgUiEventType.RUN_STARTED
        assert result.session_id == "s1"

    def test_unmapped_event_returns_none(self) -> None:
        result = project_event(
            "some.unknown.internal.event",
            session_id="s1",
        )
        assert result is None

    def test_payload_passed_through(self) -> None:
        result = project_event(
            EXECUTION_ENGINE_START,
            session_id="s1",
            payload={"task_id": "t-1", "agent_id": "a-1"},
        )
        assert result is not None
        assert result.payload["task_id"] == "t-1"

    def test_agent_id_propagated(self) -> None:
        result = project_event(
            EXECUTION_ENGINE_START,
            session_id="s1",
            agent_id="agent-eng-001",
        )
        assert result is not None
        assert result.agent_id == "agent-eng-001"

    def test_correlation_id_propagated(self) -> None:
        result = project_event(
            EXECUTION_ENGINE_START,
            session_id="s1",
            correlation_id="corr-123",
        )
        assert result is not None
        assert result.correlation_id == "corr-123"

    def test_generated_id_is_unique(self) -> None:
        r1 = project_event(EXECUTION_ENGINE_START, session_id="s1")
        r2 = project_event(EXECUTION_ENGINE_START, session_id="s1")
        assert r1 is not None
        assert r2 is not None
        assert r1.id != r2.id
