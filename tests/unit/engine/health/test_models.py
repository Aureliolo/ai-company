"""Tests for health monitoring pipeline models."""

import pytest
from pydantic import ValidationError

from synthorg.engine.health.models import (
    EscalationCause,
    EscalationSeverity,
    EscalationTicket,
)


@pytest.mark.unit
class TestEscalationSeverity:
    """EscalationSeverity enum values."""

    def test_values(self) -> None:
        assert EscalationSeverity.LOW.value == "low"
        assert EscalationSeverity.MEDIUM.value == "medium"
        assert EscalationSeverity.HIGH.value == "high"
        assert EscalationSeverity.CRITICAL.value == "critical"

    def test_member_count(self) -> None:
        assert len(EscalationSeverity) == 4


@pytest.mark.unit
class TestEscalationCause:
    """EscalationCause enum values."""

    def test_values(self) -> None:
        assert EscalationCause.STAGNATION.value == "stagnation"
        assert EscalationCause.REPEATED_FAILURE.value == "repeated_failure"
        assert EscalationCause.BUDGET_BREACH.value == "budget_breach"
        assert EscalationCause.QUALITY_DEGRADATION.value == ("quality_degradation")
        assert EscalationCause.TIMEOUT.value == "timeout"

    def test_member_count(self) -> None:
        assert len(EscalationCause) == 5


@pytest.mark.unit
class TestEscalationTicket:
    """EscalationTicket frozen model validation."""

    def test_valid_ticket(self) -> None:
        ticket = EscalationTicket(
            cause=EscalationCause.STAGNATION,
            severity=EscalationSeverity.HIGH,
            evidence="Tool repetition detected",
            agent_id="agent-1",
            task_id="task-1",
        )
        assert ticket.cause == EscalationCause.STAGNATION
        assert ticket.severity == EscalationSeverity.HIGH
        assert ticket.agent_id == "agent-1"
        assert ticket.steps_since_last_progress == 0
        assert ticket.stall_duration_seconds == 0.0
        assert ticket.quality_signals == ()
        assert ticket.id  # UUID generated

    def test_frozen(self) -> None:
        ticket = EscalationTicket(
            cause=EscalationCause.STAGNATION,
            severity=EscalationSeverity.HIGH,
            evidence="test",
            agent_id="agent-1",
            task_id="task-1",
        )
        with pytest.raises(ValidationError):
            ticket.severity = EscalationSeverity.LOW  # type: ignore[misc]

    def test_negative_steps_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EscalationTicket(
                cause=EscalationCause.STAGNATION,
                severity=EscalationSeverity.HIGH,
                evidence="test",
                agent_id="agent-1",
                task_id="task-1",
                steps_since_last_progress=-1,
            )

    def test_negative_stall_duration_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EscalationTicket(
                cause=EscalationCause.STAGNATION,
                severity=EscalationSeverity.HIGH,
                evidence="test",
                agent_id="agent-1",
                task_id="task-1",
                stall_duration_seconds=-1.0,
            )

    def test_metadata_deep_copied(self) -> None:
        meta = {"key": ["value"]}
        ticket = EscalationTicket(
            cause=EscalationCause.STAGNATION,
            severity=EscalationSeverity.HIGH,
            evidence="test",
            agent_id="agent-1",
            task_id="task-1",
            metadata=meta,
        )
        meta["key"].append("mutated")
        assert ticket.metadata == {"key": ["value"]}

    def test_unique_ids(self) -> None:
        t1 = EscalationTicket(
            cause=EscalationCause.STAGNATION,
            severity=EscalationSeverity.HIGH,
            evidence="test",
            agent_id="agent-1",
            task_id="task-1",
        )
        t2 = EscalationTicket(
            cause=EscalationCause.STAGNATION,
            severity=EscalationSeverity.HIGH,
            evidence="test",
            agent_id="agent-1",
            task_id="task-1",
        )
        assert t1.id != t2.id
