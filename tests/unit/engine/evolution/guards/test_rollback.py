"""Tests for RollbackGuard."""

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.engine.evolution.guards.rollback import RollbackGuard
from synthorg.engine.evolution.models import (
    AdaptationAxis,
    AdaptationProposal,
    AdaptationSource,
)


@pytest.mark.unit
class TestRollbackGuard:
    """Tests for RollbackGuard."""

    @pytest.fixture
    def guard(self) -> RollbackGuard:
        """Create a RollbackGuard with default config."""
        return RollbackGuard(window_tasks=20, regression_threshold=0.1)

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
    async def test_name_property(self, guard: RollbackGuard) -> None:
        """Test that the name property is non-blank."""
        assert len(guard.name) > 0
        assert "RollbackGuard" in guard.name

    @pytest.mark.asyncio
    async def test_evaluate_always_approves(
        self, guard: RollbackGuard, proposal: AdaptationProposal
    ) -> None:
        """Test that evaluate() always approves (pre-adaptation check)."""
        decision = await guard.evaluate(proposal)
        assert decision.approved is True
        assert decision.proposal_id == proposal.id

    @pytest.mark.asyncio
    async def test_check_regression_no_regression(self, guard: RollbackGuard) -> None:
        """Test that no regression is detected when quality improves."""
        agent_id: NotBlankStr = "agent-001"
        baseline_quality = 0.75
        current_quality = 0.82

        has_regression = await guard.check_regression(
            agent_id,
            baseline_quality,
            current_quality,
        )
        assert has_regression is False

    @pytest.mark.asyncio
    async def test_check_regression_detects_regression(
        self, guard: RollbackGuard
    ) -> None:
        """Test that regression is detected when quality drops."""
        agent_id: NotBlankStr = "agent-001"
        baseline_quality = 0.75
        current_quality = 0.64

        has_regression = await guard.check_regression(
            agent_id,
            baseline_quality,
            current_quality,
        )
        assert has_regression is True

    @pytest.mark.asyncio
    async def test_check_regression_at_threshold(self, guard: RollbackGuard) -> None:
        """Test regression detection at the exact threshold."""
        agent_id: NotBlankStr = "agent-001"
        baseline_quality = 0.75
        current_quality = 0.649

        has_regression = await guard.check_regression(
            agent_id,
            baseline_quality,
            current_quality,
        )
        assert has_regression is True

    @pytest.mark.asyncio
    async def test_check_regression_just_under_threshold(
        self, guard: RollbackGuard
    ) -> None:
        """Test no regression when just under the threshold."""
        agent_id: NotBlankStr = "agent-001"
        baseline_quality = 0.75
        current_quality = 0.6501

        has_regression = await guard.check_regression(
            agent_id,
            baseline_quality,
            current_quality,
        )
        assert has_regression is False

    @pytest.mark.asyncio
    async def test_check_regression_tracks_baselines(
        self, guard: RollbackGuard
    ) -> None:
        """Test that guard tracks baselines per agent."""
        agent_1_baseline = 0.75
        agent_1_current = 0.82

        agent_2_baseline = 0.80
        agent_2_current = 0.70

        regression_1 = await guard.check_regression(
            "agent-001",
            agent_1_baseline,
            agent_1_current,
        )
        assert regression_1 is False

        regression_2 = await guard.check_regression(
            "agent-002",
            agent_2_baseline,
            agent_2_current,
        )
        assert regression_2 is True

    @pytest.mark.asyncio
    async def test_check_regression_custom_threshold(self) -> None:
        """Test RollbackGuard with custom regression threshold."""
        guard = RollbackGuard(window_tasks=20, regression_threshold=0.05)

        agent_id: NotBlankStr = "agent-001"
        baseline_quality = 0.75
        current_quality = 0.69

        has_regression = await guard.check_regression(
            agent_id,
            baseline_quality,
            current_quality,
        )
        assert has_regression is True

    @pytest.mark.asyncio
    async def test_check_regression_zero_quality(self, guard: RollbackGuard) -> None:
        """Test regression detection with zero quality values."""
        agent_id: NotBlankStr = "agent-001"
        baseline_quality = 0.0
        current_quality = 0.0

        has_regression = await guard.check_regression(
            agent_id,
            baseline_quality,
            current_quality,
        )
        assert has_regression is False

    @pytest.mark.asyncio
    async def test_check_regression_high_quality(self, guard: RollbackGuard) -> None:
        """Test regression detection with high quality values."""
        agent_id: NotBlankStr = "agent-001"
        baseline_quality = 0.95
        current_quality = 0.84

        has_regression = await guard.check_regression(
            agent_id,
            baseline_quality,
            current_quality,
        )
        assert has_regression is True

    @pytest.mark.asyncio
    async def test_evaluate_multiple_proposals(self, guard: RollbackGuard) -> None:
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
