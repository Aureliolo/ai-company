"""Tests for the triage filter (conservative layer)."""

import pytest

from synthorg.engine.health.models import (
    EscalationCause,
    EscalationSeverity,
    EscalationTicket,
)
from synthorg.engine.health.triage import TriageFilter


def _ticket(
    severity: EscalationSeverity,
    *,
    stall_seconds: float = 0.0,
    steps_stuck: int = 0,
) -> EscalationTicket:
    return EscalationTicket(
        cause=EscalationCause.STAGNATION,
        severity=severity,
        evidence="test",
        agent_id="agent-1",
        task_id="task-1",
        stall_duration_seconds=stall_seconds,
        steps_since_last_progress=steps_stuck,
    )


@pytest.mark.unit
class TestTriageFilter:
    """TriageFilter escalation/dismissal rules."""

    @pytest.fixture
    def triage(self) -> TriageFilter:
        return TriageFilter()

    def test_critical_always_escalated(self, triage: TriageFilter) -> None:
        assert triage.should_escalate(_ticket(EscalationSeverity.CRITICAL))

    def test_high_always_escalated(self, triage: TriageFilter) -> None:
        assert triage.should_escalate(_ticket(EscalationSeverity.HIGH))

    def test_low_always_dismissed(self, triage: TriageFilter) -> None:
        assert not triage.should_escalate(_ticket(EscalationSeverity.LOW))

    def test_medium_short_stall_dismissed(self, triage: TriageFilter) -> None:
        assert not triage.should_escalate(
            _ticket(
                EscalationSeverity.MEDIUM,
                stall_seconds=30.0,
                steps_stuck=2,
            )
        )

    def test_medium_long_stall_escalated(self, triage: TriageFilter) -> None:
        assert triage.should_escalate(
            _ticket(
                EscalationSeverity.MEDIUM,
                stall_seconds=60.0,
                steps_stuck=0,
            )
        )

    def test_medium_many_steps_escalated(self, triage: TriageFilter) -> None:
        assert triage.should_escalate(
            _ticket(
                EscalationSeverity.MEDIUM,
                stall_seconds=10.0,
                steps_stuck=5,
            )
        )

    def test_medium_at_threshold_boundary(self, triage: TriageFilter) -> None:
        """Exactly at threshold should escalate (>=)."""
        assert triage.should_escalate(
            _ticket(
                EscalationSeverity.MEDIUM,
                stall_seconds=60.0,
            )
        )

    def test_medium_below_both_thresholds(self, triage: TriageFilter) -> None:
        assert not triage.should_escalate(
            _ticket(
                EscalationSeverity.MEDIUM,
                stall_seconds=59.9,
                steps_stuck=4,
            )
        )

    def test_custom_thresholds(self) -> None:
        triage = TriageFilter(
            stall_duration_threshold=10.0,
            steps_threshold=2,
        )
        assert triage.should_escalate(
            _ticket(
                EscalationSeverity.MEDIUM,
                stall_seconds=10.0,
            )
        )
        assert not triage.should_escalate(
            _ticket(
                EscalationSeverity.MEDIUM,
                stall_seconds=5.0,
                steps_stuck=1,
            )
        )
