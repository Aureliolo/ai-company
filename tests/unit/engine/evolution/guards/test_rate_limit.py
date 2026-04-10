"""Tests for RateLimitGuard."""

from datetime import UTC, datetime, timedelta

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.engine.evolution.guards.rate_limit import RateLimitGuard
from synthorg.engine.evolution.models import (
    AdaptationAxis,
    AdaptationProposal,
    AdaptationSource,
)


@pytest.mark.unit
class TestRateLimitGuard:
    """Tests for RateLimitGuard."""

    @pytest.fixture
    def guard(self) -> RateLimitGuard:
        """Create a RateLimitGuard with default limits."""
        return RateLimitGuard(max_per_day=3)

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
    async def test_name_property(self, guard: RateLimitGuard) -> None:
        """Test that the name property is non-blank."""
        assert len(guard.name) > 0
        assert "RateLimitGuard" in guard.name

    @pytest.mark.asyncio
    async def test_evaluate_first_adaptation_approved(
        self,
        guard: RateLimitGuard,
        proposal: AdaptationProposal,
    ) -> None:
        """Test that the first adaptation is approved."""
        decision = await guard.evaluate(proposal)
        assert decision.approved is True
        assert decision.proposal_id == proposal.id

    @pytest.mark.asyncio
    async def test_evaluate_within_limit(
        self,
        guard: RateLimitGuard,
        proposal: AdaptationProposal,
    ) -> None:
        """Test multiple adaptations within the daily limit."""
        now = datetime.now(UTC)

        decision1 = await guard.evaluate(proposal)
        assert decision1.approved is True

        proposal_2 = AdaptationProposal(
            agent_id=proposal.agent_id,
            axis=AdaptationAxis.STRATEGY_SELECTION,
            description="Second adaptation",
            changes={},
            confidence=0.8,
            source=AdaptationSource.FAILURE,
            proposed_at=now + timedelta(hours=1),
        )
        decision2 = await guard.evaluate(proposal_2)
        assert decision2.approved is True

        proposal_3 = AdaptationProposal(
            agent_id=proposal.agent_id,
            axis=AdaptationAxis.PROMPT_TEMPLATE,
            description="Third adaptation",
            changes={},
            confidence=0.7,
            source=AdaptationSource.SCHEDULED,
            proposed_at=now + timedelta(hours=2),
        )
        decision3 = await guard.evaluate(proposal_3)
        assert decision3.approved is True

    @pytest.mark.asyncio
    async def test_evaluate_exceeds_limit(
        self,
        guard: RateLimitGuard,
        proposal: AdaptationProposal,
    ) -> None:
        """Test that adaptations exceeding the daily limit are rejected."""
        now = datetime.now(UTC)

        for i in range(3):
            p = AdaptationProposal(
                agent_id=proposal.agent_id,
                axis=AdaptationAxis.IDENTITY,
                description=f"Adaptation {i}",
                changes={},
                confidence=0.9,
                source=AdaptationSource.SUCCESS,
                proposed_at=now + timedelta(hours=i),
            )
            decision = await guard.evaluate(p)
            assert decision.approved is True

        fourth_proposal = AdaptationProposal(
            agent_id=proposal.agent_id,
            axis=AdaptationAxis.IDENTITY,
            description="Fourth adaptation (should be rejected)",
            changes={},
            confidence=0.9,
            source=AdaptationSource.SUCCESS,
            proposed_at=now + timedelta(hours=3),
        )
        decision4 = await guard.evaluate(fourth_proposal)
        assert decision4.approved is False
        assert "rate" in decision4.reason.lower() or "limit" in decision4.reason.lower()

    @pytest.mark.asyncio
    async def test_evaluate_different_agents(self, guard: RateLimitGuard) -> None:
        """Test that rate limits are per-agent."""
        now = datetime.now(UTC)

        for i in range(3):
            p = AdaptationProposal(
                agent_id="agent-001",
                axis=AdaptationAxis.IDENTITY,
                description=f"Agent 1 adaptation {i}",
                changes={},
                confidence=0.9,
                source=AdaptationSource.SUCCESS,
                proposed_at=now + timedelta(hours=i),
            )
            decision = await guard.evaluate(p)
            assert decision.approved is True

        agent2_proposal = AdaptationProposal(
            agent_id="agent-002",
            axis=AdaptationAxis.IDENTITY,
            description="Agent 2 adaptation",
            changes={},
            confidence=0.9,
            source=AdaptationSource.SUCCESS,
            proposed_at=now + timedelta(hours=10),
        )
        decision2 = await guard.evaluate(agent2_proposal)
        assert decision2.approved is True

    @pytest.mark.asyncio
    async def test_evaluate_cleanup_old_timestamps(self, guard: RateLimitGuard) -> None:
        """Test that timestamps older than 24h are cleaned up."""
        now = datetime.now(UTC)
        old_time = now - timedelta(days=2)

        old_proposal = AdaptationProposal(
            agent_id="agent-001",
            axis=AdaptationAxis.IDENTITY,
            description="Old adaptation",
            changes={},
            confidence=0.9,
            source=AdaptationSource.SUCCESS,
            proposed_at=old_time,
        )

        await guard.evaluate(old_proposal)

        recent_proposal_1 = AdaptationProposal(
            agent_id="agent-001",
            axis=AdaptationAxis.IDENTITY,
            description="Recent 1",
            changes={},
            confidence=0.9,
            source=AdaptationSource.SUCCESS,
            proposed_at=now,
        )
        await guard.evaluate(recent_proposal_1)

        recent_proposal_2 = AdaptationProposal(
            agent_id="agent-001",
            axis=AdaptationAxis.IDENTITY,
            description="Recent 2",
            changes={},
            confidence=0.9,
            source=AdaptationSource.SUCCESS,
            proposed_at=now + timedelta(hours=1),
        )
        await guard.evaluate(recent_proposal_2)

        recent_proposal_3 = AdaptationProposal(
            agent_id="agent-001",
            axis=AdaptationAxis.IDENTITY,
            description="Recent 3",
            changes={},
            confidence=0.9,
            source=AdaptationSource.SUCCESS,
            proposed_at=now + timedelta(hours=2),
        )
        decision3 = await guard.evaluate(recent_proposal_3)
        assert decision3.approved is True

        recent_proposal_4 = AdaptationProposal(
            agent_id="agent-001",
            axis=AdaptationAxis.IDENTITY,
            description="Recent 4 (should be rejected)",
            changes={},
            confidence=0.9,
            source=AdaptationSource.SUCCESS,
            proposed_at=now + timedelta(hours=3),
        )
        decision4 = await guard.evaluate(recent_proposal_4)
        assert decision4.approved is False

    @pytest.mark.asyncio
    async def test_evaluate_custom_max_per_day(self) -> None:
        """Test RateLimitGuard with custom max_per_day."""
        guard = RateLimitGuard(max_per_day=1)
        now = datetime.now(UTC)

        proposal1 = AdaptationProposal(
            agent_id="agent-001",
            axis=AdaptationAxis.IDENTITY,
            description="First",
            changes={},
            confidence=0.9,
            source=AdaptationSource.SUCCESS,
            proposed_at=now,
        )
        decision1 = await guard.evaluate(proposal1)
        assert decision1.approved is True

        proposal2 = AdaptationProposal(
            agent_id="agent-001",
            axis=AdaptationAxis.IDENTITY,
            description="Second (should be rejected)",
            changes={},
            confidence=0.9,
            source=AdaptationSource.SUCCESS,
            proposed_at=now + timedelta(hours=1),
        )
        decision2 = await guard.evaluate(proposal2)
        assert decision2.approved is False
