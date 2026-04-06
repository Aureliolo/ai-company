"""Tests for the health judge (sensitive layer)."""

import pytest

from synthorg.engine.health.judge import HealthJudge
from synthorg.engine.health.models import EscalationCause, EscalationSeverity
from synthorg.engine.loop_protocol import TerminationReason
from synthorg.engine.quality.models import StepQuality, StepQualitySignal


def _signal(quality: StepQuality, step_index: int = 0) -> StepQualitySignal:
    return StepQualitySignal(
        quality=quality,
        confidence=0.7,
        reason="test",
        step_index=step_index,
        turn_range=(1, 1),
    )


@pytest.mark.unit
class TestHealthJudge:
    """HealthJudge emission rules."""

    @pytest.fixture
    def judge(self) -> HealthJudge:
        return HealthJudge()

    def test_stagnation_emits_high_ticket(self, judge: HealthJudge) -> None:
        ticket = judge.emit_ticket(
            termination_reason=TerminationReason.STAGNATION,
            agent_id="agent-1",
            task_id="task-1",
            execution_duration=30.0,
        )
        assert ticket is not None
        assert ticket.cause == EscalationCause.STAGNATION
        assert ticket.severity == EscalationSeverity.HIGH
        assert ticket.stall_duration_seconds == 30.0

    def test_error_with_recovery_emits_medium(self, judge: HealthJudge) -> None:
        ticket = judge.emit_ticket(
            termination_reason=TerminationReason.ERROR,
            has_recovery=True,
            agent_id="agent-1",
            task_id="task-1",
        )
        assert ticket is not None
        assert ticket.cause == EscalationCause.REPEATED_FAILURE
        assert ticket.severity == EscalationSeverity.MEDIUM

    def test_error_without_recovery_no_ticket(self, judge: HealthJudge) -> None:
        ticket = judge.emit_ticket(
            termination_reason=TerminationReason.ERROR,
            has_recovery=False,
            agent_id="agent-1",
            task_id="task-1",
        )
        assert ticket is None

    def test_completed_no_ticket(self, judge: HealthJudge) -> None:
        ticket = judge.emit_ticket(
            termination_reason=TerminationReason.COMPLETED,
            agent_id="agent-1",
            task_id="task-1",
        )
        assert ticket is None

    def test_quality_degradation_threshold_met(self, judge: HealthJudge) -> None:
        signals = tuple(_signal(StepQuality.INCORRECT, i) for i in range(3))
        ticket = judge.emit_ticket(
            termination_reason=TerminationReason.COMPLETED,
            quality_signals=signals,
            agent_id="agent-1",
            task_id="task-1",
        )
        assert ticket is not None
        assert ticket.cause == EscalationCause.QUALITY_DEGRADATION
        assert ticket.severity == EscalationSeverity.HIGH
        assert ticket.steps_since_last_progress == 3

    def test_quality_degradation_below_threshold(self, judge: HealthJudge) -> None:
        signals = (
            _signal(StepQuality.INCORRECT, 0),
            _signal(StepQuality.INCORRECT, 1),
        )
        ticket = judge.emit_ticket(
            termination_reason=TerminationReason.COMPLETED,
            quality_signals=signals,
            agent_id="agent-1",
            task_id="task-1",
        )
        assert ticket is None

    def test_quality_degradation_non_trailing_ignored(self, judge: HealthJudge) -> None:
        """Only trailing INCORRECT signals count."""
        signals = (
            _signal(StepQuality.INCORRECT, 0),
            _signal(StepQuality.INCORRECT, 1),
            _signal(StepQuality.INCORRECT, 2),
            _signal(StepQuality.CORRECT, 3),
        )
        ticket = judge.emit_ticket(
            termination_reason=TerminationReason.COMPLETED,
            quality_signals=signals,
            agent_id="agent-1",
            task_id="task-1",
        )
        assert ticket is None

    def test_quality_degradation_critical_at_double_threshold(
        self, judge: HealthJudge
    ) -> None:
        signals = tuple(_signal(StepQuality.INCORRECT, i) for i in range(6))
        ticket = judge.emit_ticket(
            termination_reason=TerminationReason.COMPLETED,
            quality_signals=signals,
            agent_id="agent-1",
            task_id="task-1",
        )
        assert ticket is not None
        assert ticket.severity == EscalationSeverity.CRITICAL

    def test_custom_quality_threshold(self) -> None:
        judge = HealthJudge(quality_degradation_threshold=1)
        signals = (_signal(StepQuality.INCORRECT, 0),)
        ticket = judge.emit_ticket(
            termination_reason=TerminationReason.COMPLETED,
            quality_signals=signals,
            agent_id="agent-1",
            task_id="task-1",
        )
        assert ticket is not None

    def test_stagnation_priority_over_quality(self, judge: HealthJudge) -> None:
        """Stagnation check runs before quality degradation."""
        signals = tuple(_signal(StepQuality.INCORRECT, i) for i in range(5))
        ticket = judge.emit_ticket(
            termination_reason=TerminationReason.STAGNATION,
            quality_signals=signals,
            agent_id="agent-1",
            task_id="task-1",
        )
        assert ticket is not None
        assert ticket.cause == EscalationCause.STAGNATION

    def test_quality_signals_attached(self, judge: HealthJudge) -> None:
        signals = tuple(_signal(StepQuality.INCORRECT, i) for i in range(3))
        ticket = judge.emit_ticket(
            termination_reason=TerminationReason.COMPLETED,
            quality_signals=signals,
            agent_id="agent-1",
            task_id="task-1",
        )
        assert ticket is not None
        assert len(ticket.quality_signals) == 3
