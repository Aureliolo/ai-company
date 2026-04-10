"""Tests for ReviewGateGuard."""

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.engine.evolution.guards.review_gate import ReviewGateGuard
from synthorg.engine.evolution.models import (
    AdaptationAxis,
    AdaptationProposal,
    AdaptationSource,
)


@pytest.mark.unit
class TestReviewGateGuard:
    """Tests for ReviewGateGuard."""

    @pytest.fixture
    def guard(self) -> ReviewGateGuard:
        """Create a ReviewGateGuard with default config."""
        return ReviewGateGuard(
            require_review_for=(AdaptationAxis.IDENTITY,),
        )

    @pytest.fixture
    def identity_proposal(self) -> AdaptationProposal:
        """Create an IDENTITY adaptation proposal."""
        agent_id: NotBlankStr = "agent-001"
        return AdaptationProposal(
            agent_id=agent_id,
            axis=AdaptationAxis.IDENTITY,
            description="Update agent identity",
            changes={"name": "Bob"},
            confidence=0.9,
            source=AdaptationSource.SUCCESS,
        )

    @pytest.fixture
    def strategy_proposal(self) -> AdaptationProposal:
        """Create a STRATEGY_SELECTION adaptation proposal."""
        agent_id: NotBlankStr = "agent-001"
        return AdaptationProposal(
            agent_id=agent_id,
            axis=AdaptationAxis.STRATEGY_SELECTION,
            description="Update strategy",
            changes={"strategy": "new_approach"},
            confidence=0.85,
            source=AdaptationSource.FAILURE,
        )

    @pytest.mark.asyncio
    async def test_name_property(self, guard: ReviewGateGuard) -> None:
        """Test that the name property is non-blank."""
        assert len(guard.name) > 0
        assert "ReviewGateGuard" in guard.name

    @pytest.mark.asyncio
    async def test_evaluate_identity_requires_review(
        self, guard: ReviewGateGuard, identity_proposal: AdaptationProposal
    ) -> None:
        """Test that IDENTITY adaptations are rejected (require review)."""
        decision = await guard.evaluate(identity_proposal)
        assert decision.approved is False
        assert "human" in decision.reason.lower() or "review" in decision.reason.lower()
        assert decision.proposal_id == identity_proposal.id

    @pytest.mark.asyncio
    async def test_evaluate_strategy_auto_approved(
        self, guard: ReviewGateGuard, strategy_proposal: AdaptationProposal
    ) -> None:
        """Test that STRATEGY_SELECTION adaptations are auto-approved."""
        decision = await guard.evaluate(strategy_proposal)
        assert decision.approved is True
        assert decision.proposal_id == strategy_proposal.id

    @pytest.mark.asyncio
    async def test_evaluate_prompt_auto_approved(self, guard: ReviewGateGuard) -> None:
        """Test that PROMPT_TEMPLATE adaptations are auto-approved."""
        prompt_proposal = AdaptationProposal(
            agent_id="agent-001",
            axis=AdaptationAxis.PROMPT_TEMPLATE,
            description="Update prompt",
            changes={"instruction": "Be thorough"},
            confidence=0.8,
            source=AdaptationSource.SCHEDULED,
        )
        decision = await guard.evaluate(prompt_proposal)
        assert decision.approved is True

    @pytest.mark.asyncio
    async def test_evaluate_multiple_require_review(self) -> None:
        """Test ReviewGateGuard that requires review for multiple axes."""
        guard = ReviewGateGuard(
            require_review_for=(
                AdaptationAxis.IDENTITY,
                AdaptationAxis.STRATEGY_SELECTION,
            ),
        )

        identity_proposal = AdaptationProposal(
            agent_id="agent-001",
            axis=AdaptationAxis.IDENTITY,
            description="Update identity",
            changes={},
            confidence=0.9,
            source=AdaptationSource.SUCCESS,
        )
        decision_id = await guard.evaluate(identity_proposal)
        assert decision_id.approved is False

        strategy_proposal = AdaptationProposal(
            agent_id="agent-001",
            axis=AdaptationAxis.STRATEGY_SELECTION,
            description="Update strategy",
            changes={},
            confidence=0.85,
            source=AdaptationSource.FAILURE,
        )
        decision_strategy = await guard.evaluate(strategy_proposal)
        assert decision_strategy.approved is False

        prompt_proposal = AdaptationProposal(
            agent_id="agent-001",
            axis=AdaptationAxis.PROMPT_TEMPLATE,
            description="Update prompt",
            changes={},
            confidence=0.8,
            source=AdaptationSource.SCHEDULED,
        )
        decision_prompt = await guard.evaluate(prompt_proposal)
        assert decision_prompt.approved is True

    @pytest.mark.asyncio
    async def test_evaluate_empty_require_review(self) -> None:
        """Test ReviewGateGuard that doesn't require review for any axis."""
        guard = ReviewGateGuard(require_review_for=())

        identity_proposal = AdaptationProposal(
            agent_id="agent-001",
            axis=AdaptationAxis.IDENTITY,
            description="Update identity",
            changes={},
            confidence=0.9,
            source=AdaptationSource.SUCCESS,
        )
        decision = await guard.evaluate(identity_proposal)
        assert decision.approved is True
