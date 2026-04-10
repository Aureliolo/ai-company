"""Tests for ShadowEvaluationGuard."""

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.engine.evolution.guards.shadow_evaluation import (
    ShadowEvaluationGuard,
)
from synthorg.engine.evolution.models import (
    AdaptationAxis,
    AdaptationProposal,
    AdaptationSource,
)


@pytest.mark.unit
class TestShadowEvaluationGuard:
    """Tests for ShadowEvaluationGuard."""

    @pytest.fixture
    def guard(self) -> ShadowEvaluationGuard:
        """Create a ShadowEvaluationGuard."""
        return ShadowEvaluationGuard()

    @pytest.fixture
    def proposal(self) -> AdaptationProposal:
        """Create a sample adaptation proposal."""
        agent_id: NotBlankStr = "agent-001"
        return AdaptationProposal(
            agent_id=agent_id,
            axis=AdaptationAxis.IDENTITY,
            description="Test adaptation",
            changes={},
            confidence=0.9,
            source=AdaptationSource.SUCCESS,
        )

    @pytest.mark.asyncio
    async def test_name_property(self, guard: ShadowEvaluationGuard) -> None:
        """Test that the name property is non-blank."""
        assert len(guard.name) > 0
        assert "ShadowEvaluationGuard" in guard.name

    @pytest.mark.asyncio
    async def test_evaluate_always_approves(
        self,
        guard: ShadowEvaluationGuard,
        proposal: AdaptationProposal,
    ) -> None:
        """Test that evaluate() always approves with placeholder message."""
        decision = await guard.evaluate(proposal)
        assert decision.approved is True
        assert decision.proposal_id == proposal.id
        assert (
            "not yet implemented" in decision.reason.lower()
            or "shadow" in decision.reason.lower()
        )

    @pytest.mark.asyncio
    async def test_evaluate_identity_axis(self, guard: ShadowEvaluationGuard) -> None:
        """Test evaluate() on IDENTITY axis."""
        proposal = AdaptationProposal(
            agent_id="agent-001",
            axis=AdaptationAxis.IDENTITY,
            description="Update identity",
            changes={"name": "Bob"},
            confidence=0.9,
            source=AdaptationSource.SUCCESS,
        )
        decision = await guard.evaluate(proposal)
        assert decision.approved is True

    @pytest.mark.asyncio
    async def test_evaluate_strategy_axis(self, guard: ShadowEvaluationGuard) -> None:
        """Test evaluate() on STRATEGY_SELECTION axis."""
        proposal = AdaptationProposal(
            agent_id="agent-001",
            axis=AdaptationAxis.STRATEGY_SELECTION,
            description="Update strategy",
            changes={"strategy": "new_approach"},
            confidence=0.85,
            source=AdaptationSource.FAILURE,
        )
        decision = await guard.evaluate(proposal)
        assert decision.approved is True

    @pytest.mark.asyncio
    async def test_evaluate_prompt_axis(self, guard: ShadowEvaluationGuard) -> None:
        """Test evaluate() on PROMPT_TEMPLATE axis."""
        proposal = AdaptationProposal(
            agent_id="agent-001",
            axis=AdaptationAxis.PROMPT_TEMPLATE,
            description="Update prompt",
            changes={"instruction": "Be thorough"},
            confidence=0.8,
            source=AdaptationSource.SCHEDULED,
        )
        decision = await guard.evaluate(proposal)
        assert decision.approved is True

    @pytest.mark.asyncio
    async def test_evaluate_multiple_proposals(
        self,
        guard: ShadowEvaluationGuard,
    ) -> None:
        """Test evaluate() on multiple proposals always approves."""
        proposals = [
            AdaptationProposal(
                agent_id="agent-001",
                axis=AdaptationAxis.IDENTITY,
                description=f"Proposal {i}",
                changes={},
                confidence=0.9,
                source=AdaptationSource.SUCCESS,
            )
            for i in range(5)
        ]

        for proposal in proposals:
            decision = await guard.evaluate(proposal)
            assert decision.approved is True
            assert (
                "not yet implemented" in decision.reason.lower()
                or "shadow" in decision.reason.lower()
            )
