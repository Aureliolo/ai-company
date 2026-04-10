"""Tests for the CompositeProposer."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from synthorg.core.agent import AgentIdentity
from synthorg.core.types import NotBlankStr
from synthorg.engine.evolution.models import (
    AdaptationAxis,
    AdaptationProposal,
    AdaptationSource,
)
from synthorg.engine.evolution.proposers.composite import CompositeProposer
from synthorg.engine.evolution.protocols import EvolutionContext
from synthorg.hr.performance.models import AgentPerformanceSnapshot


@pytest.mark.unit
class TestCompositeProposer:
    """Test suite for CompositeProposer."""

    @pytest.fixture
    def mock_failure_proposer(self) -> AsyncMock:
        """Create a mock failure proposer."""
        proposer = AsyncMock()
        proposer.name = "mock_failure"
        return proposer

    @pytest.fixture
    def mock_success_proposer(self) -> AsyncMock:
        """Create a mock success proposer."""
        proposer = AsyncMock()
        proposer.name = "mock_success"
        return proposer

    @pytest.fixture
    def composite_proposer(
        self,
        mock_failure_proposer: AsyncMock,
        mock_success_proposer: AsyncMock,
    ) -> CompositeProposer:
        """Create a CompositeProposer instance."""
        return CompositeProposer(
            failure_proposer=mock_failure_proposer,
            success_proposer=mock_success_proposer,
        )

    @pytest.fixture
    def mock_identity(self) -> AgentIdentity:
        """Create a mock agent identity."""
        identity = MagicMock(spec=AgentIdentity)
        identity.name = NotBlankStr("test-agent")
        identity.version = 1
        identity.role = "test_role"
        identity.autonomy_level = None
        identity.seniority = "junior"
        return identity

    @pytest.mark.asyncio
    async def test_name_property(
        self,
        composite_proposer: CompositeProposer,
    ) -> None:
        """Test that the proposer returns correct name."""
        assert composite_proposer.name == "composite"

    @pytest.mark.asyncio
    async def test_propose_uses_success_proposer_when_no_decline(
        self,
        composite_proposer: CompositeProposer,
        mock_failure_proposer: AsyncMock,
        mock_success_proposer: AsyncMock,
        mock_identity: AgentIdentity,
    ) -> None:
        """Test that success proposer is used when no declining trend."""
        success_proposal = AdaptationProposal(
            agent_id=NotBlankStr("test-agent"),
            axis=AdaptationAxis.STRATEGY_SELECTION,
            description=NotBlankStr("success proposal"),
            confidence=0.8,
            source=AdaptationSource.SUCCESS,
        )
        mock_success_proposer.propose.return_value = (success_proposal,)
        mock_failure_proposer.propose.return_value = ()

        snapshot = MagicMock(spec=AgentPerformanceSnapshot)
        snapshot.overall_quality_score = 8.0
        snapshot.agent_id = NotBlankStr("test-agent")

        context = EvolutionContext(
            agent_id=NotBlankStr("test-agent"),
            identity=mock_identity,
            performance_snapshot=snapshot,
            recent_task_results=(),
            recent_procedural_memories=(),
        )

        proposals = await composite_proposer.propose(
            agent_id=context.agent_id,
            context=context,
        )

        # Should only call success proposer
        assert len(proposals) == 1
        assert proposals[0] == success_proposal
        mock_success_proposer.propose.assert_called_once()
        mock_failure_proposer.propose.assert_not_called()

    @pytest.mark.asyncio
    async def test_propose_uses_failure_proposer_on_decline(
        self,
        composite_proposer: CompositeProposer,
        mock_failure_proposer: AsyncMock,
        mock_success_proposer: AsyncMock,
        mock_identity: AgentIdentity,
    ) -> None:
        """Test that failure proposer is used when declining trend detected."""
        failure_proposal = AdaptationProposal(
            agent_id=NotBlankStr("test-agent"),
            axis=AdaptationAxis.PROMPT_TEMPLATE,
            description=NotBlankStr("failure proposal"),
            confidence=0.7,
            source=AdaptationSource.FAILURE,
        )
        mock_failure_proposer.propose.return_value = (failure_proposal,)
        mock_success_proposer.propose.return_value = ()

        # Create a low quality snapshot to trigger failure path
        snapshot = MagicMock(spec=AgentPerformanceSnapshot)
        snapshot.overall_quality_score = 3.0
        snapshot.agent_id = NotBlankStr("test-agent")

        context = EvolutionContext(
            agent_id=NotBlankStr("test-agent"),
            identity=mock_identity,
            performance_snapshot=snapshot,
            recent_task_results=(),
            recent_procedural_memories=(),
        )

        proposals = await composite_proposer.propose(
            agent_id=context.agent_id,
            context=context,
        )

        # Should only call failure proposer
        assert len(proposals) == 1
        assert proposals[0] == failure_proposal
        mock_failure_proposer.propose.assert_called_once()
        mock_success_proposer.propose.assert_not_called()

    @pytest.mark.asyncio
    async def test_propose_routes_to_failure_on_low_quality(
        self,
        composite_proposer: CompositeProposer,
        mock_failure_proposer: AsyncMock,
        mock_success_proposer: AsyncMock,
        mock_identity: AgentIdentity,
    ) -> None:
        """Test that composite proposer routes to failure path on low quality."""
        failure_proposal1 = AdaptationProposal(
            agent_id=NotBlankStr("test-agent"),
            axis=AdaptationAxis.PROMPT_TEMPLATE,
            description=NotBlankStr("failure proposal 1"),
            confidence=0.6,
            source=AdaptationSource.FAILURE,
        )
        failure_proposal2 = AdaptationProposal(
            agent_id=NotBlankStr("test-agent"),
            axis=AdaptationAxis.STRATEGY_SELECTION,
            description=NotBlankStr("failure proposal 2"),
            confidence=0.7,
            source=AdaptationSource.FAILURE,
        )

        mock_failure_proposer.propose.return_value = (
            failure_proposal1,
            failure_proposal2,
        )
        mock_success_proposer.propose.return_value = ()

        snapshot = MagicMock(spec=AgentPerformanceSnapshot)
        snapshot.overall_quality_score = 3.0
        snapshot.agent_id = NotBlankStr("test-agent")

        context = EvolutionContext(
            agent_id=NotBlankStr("test-agent"),
            identity=mock_identity,
            performance_snapshot=snapshot,
            recent_task_results=(),
            recent_procedural_memories=(),
        )

        proposals = await composite_proposer.propose(
            agent_id=context.agent_id,
            context=context,
        )

        # Should route to failure proposer and return its proposals
        assert len(proposals) == 2
        assert all(p.source == AdaptationSource.FAILURE for p in proposals)
        # Success proposer should not be called
        mock_success_proposer.propose.assert_not_called()

    @pytest.mark.asyncio
    async def test_propose_empty_from_both(
        self,
        composite_proposer: CompositeProposer,
        mock_failure_proposer: AsyncMock,
        mock_success_proposer: AsyncMock,
        mock_identity: AgentIdentity,
    ) -> None:
        """Test that empty results from both proposers yield empty tuple."""
        mock_failure_proposer.propose.return_value = ()
        mock_success_proposer.propose.return_value = ()

        snapshot = MagicMock(spec=AgentPerformanceSnapshot)
        snapshot.overall_quality_score = 8.0
        snapshot.agent_id = NotBlankStr("test-agent")

        context = EvolutionContext(
            agent_id=NotBlankStr("test-agent"),
            identity=mock_identity,
            performance_snapshot=snapshot,
            recent_task_results=(),
            recent_procedural_memories=(),
        )

        proposals = await composite_proposer.propose(
            agent_id=context.agent_id,
            context=context,
        )

        assert proposals == ()

    @pytest.mark.asyncio
    async def test_propose_none_performance_snapshot(
        self,
        composite_proposer: CompositeProposer,
        mock_failure_proposer: AsyncMock,
        mock_success_proposer: AsyncMock,
        mock_identity: AgentIdentity,
    ) -> None:
        """Test that None performance snapshot routes to success proposer."""
        success_proposal = AdaptationProposal(
            agent_id=NotBlankStr("test-agent"),
            axis=AdaptationAxis.STRATEGY_SELECTION,
            description=NotBlankStr("success proposal"),
            confidence=0.8,
            source=AdaptationSource.SUCCESS,
        )
        mock_success_proposer.propose.return_value = (success_proposal,)
        mock_failure_proposer.propose.return_value = ()

        context = EvolutionContext(
            agent_id=NotBlankStr("test-agent"),
            identity=mock_identity,
            performance_snapshot=None,
            recent_task_results=(),
            recent_procedural_memories=(),
        )

        await composite_proposer.propose(
            agent_id=context.agent_id,
            context=context,
        )

        # With no performance data, should use success path (optimistic)
        mock_success_proposer.propose.assert_called_once()
