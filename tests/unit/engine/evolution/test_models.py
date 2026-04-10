"""Tests for evolution domain models."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from synthorg.engine.evolution.models import (
    AdaptationAxis,
    AdaptationDecision,
    AdaptationProposal,
    AdaptationSource,
    EvolutionEvent,
)


class TestAdaptationAxis:
    """AdaptationAxis enum values."""

    @pytest.mark.unit
    def test_values(self) -> None:
        assert AdaptationAxis.IDENTITY.value == "identity"
        assert AdaptationAxis.STRATEGY_SELECTION.value == "strategy_selection"
        assert AdaptationAxis.PROMPT_TEMPLATE.value == "prompt_template"

    @pytest.mark.unit
    def test_all_values_present(self) -> None:
        assert len(AdaptationAxis) == 3


class TestAdaptationSource:
    """AdaptationSource enum values."""

    @pytest.mark.unit
    def test_values(self) -> None:
        assert AdaptationSource.FAILURE.value == "failure"
        assert AdaptationSource.SUCCESS.value == "success"
        assert AdaptationSource.INFLECTION.value == "inflection"
        assert AdaptationSource.SCHEDULED.value == "scheduled"


class TestAdaptationProposal:
    """AdaptationProposal model validation."""

    @pytest.mark.unit
    def test_minimal_valid(self) -> None:
        p = AdaptationProposal(
            agent_id="agent-1",
            axis=AdaptationAxis.PROMPT_TEMPLATE,
            description="inject learned prompt",
            confidence=0.8,
            source=AdaptationSource.SUCCESS,
        )
        assert p.agent_id == "agent-1"
        assert p.axis == AdaptationAxis.PROMPT_TEMPLATE
        assert p.confidence == 0.8
        assert p.changes == {}
        assert p.proposed_at.tzinfo is not None

    @pytest.mark.unit
    def test_frozen(self) -> None:
        p = AdaptationProposal(
            agent_id="agent-1",
            axis=AdaptationAxis.IDENTITY,
            description="update skills",
            confidence=0.9,
            source=AdaptationSource.FAILURE,
        )
        with pytest.raises(ValueError, match="frozen"):
            p.confidence = 0.5  # type: ignore[misc]

    @pytest.mark.unit
    def test_confidence_bounds(self) -> None:
        with pytest.raises(ValueError, match="greater than or equal"):
            AdaptationProposal(
                agent_id="agent-1",
                axis=AdaptationAxis.IDENTITY,
                description="bad",
                confidence=-0.1,
                source=AdaptationSource.FAILURE,
            )
        with pytest.raises(ValueError, match="less than or equal"):
            AdaptationProposal(
                agent_id="agent-1",
                axis=AdaptationAxis.IDENTITY,
                description="bad",
                confidence=1.1,
                source=AdaptationSource.FAILURE,
            )

    @pytest.mark.unit
    def test_blank_agent_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="whitespace"):
            AdaptationProposal(
                agent_id="   ",
                axis=AdaptationAxis.IDENTITY,
                description="test",
                confidence=0.5,
                source=AdaptationSource.FAILURE,
            )

    @pytest.mark.unit
    def test_with_changes(self) -> None:
        p = AdaptationProposal(
            agent_id="agent-1",
            axis=AdaptationAxis.IDENTITY,
            description="add python skill",
            changes={"skills.primary": ["python", "go"]},
            confidence=0.95,
            source=AdaptationSource.SUCCESS,
        )
        assert p.changes == {"skills.primary": ["python", "go"]}

    @pytest.mark.unit
    def test_nan_rejected(self) -> None:
        with pytest.raises(ValueError, match="finite"):
            AdaptationProposal(
                agent_id="agent-1",
                axis=AdaptationAxis.IDENTITY,
                description="bad",
                confidence=float("nan"),
                source=AdaptationSource.FAILURE,
            )


class TestAdaptationDecision:
    """AdaptationDecision model validation."""

    @pytest.mark.unit
    def test_approval(self) -> None:
        d = AdaptationDecision(
            proposal_id=uuid4(),
            approved=True,
            guard_name="rate_limit",
            reason="within daily limit",
        )
        assert d.approved is True
        assert d.guard_name == "rate_limit"

    @pytest.mark.unit
    def test_rejection(self) -> None:
        d = AdaptationDecision(
            proposal_id=uuid4(),
            approved=False,
            guard_name="review_gate",
            reason="identity changes require human approval",
        )
        assert d.approved is False


class TestEvolutionEvent:
    """EvolutionEvent model validation."""

    @pytest.mark.unit
    def test_non_identity_event_no_versions_required(self) -> None:
        proposal = AdaptationProposal(
            agent_id="agent-1",
            axis=AdaptationAxis.PROMPT_TEMPLATE,
            description="inject prompt",
            confidence=0.8,
            source=AdaptationSource.SUCCESS,
        )
        decision = AdaptationDecision(
            proposal_id=proposal.id,
            approved=True,
            guard_name="rate_limit",
            reason="ok",
        )
        event = EvolutionEvent(
            agent_id="agent-1",
            proposal=proposal,
            decision=decision,
            applied=True,
        )
        assert event.applied is True
        assert event.identity_version_before is None
        assert event.identity_version_after is None

    @pytest.mark.unit
    def test_identity_event_requires_versions_when_applied(self) -> None:
        proposal = AdaptationProposal(
            agent_id="agent-1",
            axis=AdaptationAxis.IDENTITY,
            description="update skills",
            confidence=0.9,
            source=AdaptationSource.FAILURE,
        )
        decision = AdaptationDecision(
            proposal_id=proposal.id,
            approved=True,
            guard_name="composite",
            reason="all guards passed",
        )
        with pytest.raises(
            ValueError,
            match="identity_version_before is required",
        ):
            EvolutionEvent(
                agent_id="agent-1",
                proposal=proposal,
                decision=decision,
                applied=True,
            )

    @pytest.mark.unit
    def test_identity_event_requires_after_version(self) -> None:
        proposal = AdaptationProposal(
            agent_id="agent-1",
            axis=AdaptationAxis.IDENTITY,
            description="update skills",
            confidence=0.9,
            source=AdaptationSource.FAILURE,
        )
        decision = AdaptationDecision(
            proposal_id=proposal.id,
            approved=True,
            guard_name="composite",
            reason="all guards passed",
        )
        with pytest.raises(
            ValueError,
            match="identity_version_after is required",
        ):
            EvolutionEvent(
                agent_id="agent-1",
                proposal=proposal,
                decision=decision,
                applied=True,
                identity_version_before=1,
            )

    @pytest.mark.unit
    def test_identity_event_with_versions(self) -> None:
        proposal = AdaptationProposal(
            agent_id="agent-1",
            axis=AdaptationAxis.IDENTITY,
            description="update skills",
            confidence=0.9,
            source=AdaptationSource.FAILURE,
        )
        decision = AdaptationDecision(
            proposal_id=proposal.id,
            approved=True,
            guard_name="composite",
            reason="all guards passed",
        )
        event = EvolutionEvent(
            agent_id="agent-1",
            proposal=proposal,
            decision=decision,
            applied=True,
            identity_version_before=1,
            identity_version_after=2,
        )
        assert event.identity_version_before == 1
        assert event.identity_version_after == 2

    @pytest.mark.unit
    def test_rejected_identity_no_versions_needed(self) -> None:
        """Rejected proposals don't need version fields."""
        proposal = AdaptationProposal(
            agent_id="agent-1",
            axis=AdaptationAxis.IDENTITY,
            description="update skills",
            confidence=0.9,
            source=AdaptationSource.FAILURE,
        )
        decision = AdaptationDecision(
            proposal_id=proposal.id,
            approved=False,
            guard_name="review_gate",
            reason="denied",
        )
        event = EvolutionEvent(
            agent_id="agent-1",
            proposal=proposal,
            decision=decision,
            applied=False,
        )
        assert event.applied is False
        assert event.identity_version_before is None

    @pytest.mark.unit
    def test_default_timestamps(self) -> None:
        now = datetime.now(UTC)
        proposal = AdaptationProposal(
            agent_id="agent-1",
            axis=AdaptationAxis.PROMPT_TEMPLATE,
            description="test",
            confidence=0.5,
            source=AdaptationSource.SCHEDULED,
        )
        assert proposal.proposed_at >= now

        decision = AdaptationDecision(
            proposal_id=proposal.id,
            approved=True,
            guard_name="test",
            reason="ok",
        )
        assert decision.decided_at >= now

        event = EvolutionEvent(
            agent_id="agent-1",
            proposal=proposal,
            decision=decision,
            applied=True,
        )
        assert event.event_at >= now
