"""Tests for the SelfReportProposer."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from synthorg.core.agent import AgentIdentity
from synthorg.core.types import NotBlankStr
from synthorg.engine.evolution.models import (
    AdaptationAxis,
    AdaptationSource,
)
from synthorg.engine.evolution.proposers.self_report import SelfReportProposer
from synthorg.engine.evolution.protocols import EvolutionContext
from synthorg.hr.performance.models import (
    AgentPerformanceSnapshot,
)
from synthorg.memory.models import MemoryEntry


@pytest.mark.unit
class TestSelfReportProposer:
    """Test suite for SelfReportProposer."""

    @pytest.fixture
    def mock_provider(self) -> AsyncMock:
        """Create a mock completion provider."""
        return AsyncMock()

    @pytest.fixture
    def proposer(self, mock_provider: AsyncMock) -> SelfReportProposer:
        """Create a SelfReportProposer instance."""
        return SelfReportProposer(
            mock_provider,
            model="test-model",
            temperature=0.3,
            max_tokens=1000,
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
    async def test_name_property(self, proposer: SelfReportProposer) -> None:
        """Test that the proposer returns correct name."""
        assert proposer.name == "self_report"

    @pytest.mark.asyncio
    async def test_propose_no_performance_data(
        self,
        proposer: SelfReportProposer,
        mock_identity: AgentIdentity,
    ) -> None:
        """Test propose with no performance data returns empty tuple."""
        context = EvolutionContext(
            agent_id=NotBlankStr("test-agent"),
            identity=mock_identity,
            performance_snapshot=None,
            recent_task_results=(),
            recent_procedural_memories=(),
        )

        proposals = await proposer.propose(
            agent_id=context.agent_id,
            context=context,
        )

        assert proposals == ()

    @pytest.mark.asyncio
    async def test_propose_high_quality_suggests_strategy(
        self,
        proposer: SelfReportProposer,
        mock_identity: AgentIdentity,
    ) -> None:
        """Test that high quality (>9.0) suggests strategy adaptation."""
        snapshot = MagicMock(spec=AgentPerformanceSnapshot)
        snapshot.overall_quality_score = 9.5
        snapshot.agent_id = NotBlankStr("test-agent")

        context = EvolutionContext(
            agent_id=NotBlankStr("test-agent"),
            identity=mock_identity,
            performance_snapshot=snapshot,
            recent_task_results=(),
            recent_procedural_memories=(),
        )

        proposals = await proposer.propose(
            agent_id=context.agent_id,
            context=context,
        )

        # Should have at least one strategy adaptation proposal
        assert any(p.axis == AdaptationAxis.STRATEGY_SELECTION for p in proposals)

    @pytest.mark.asyncio
    async def test_propose_no_adaptation_for_medium_quality(
        self,
        proposer: SelfReportProposer,
        mock_identity: AgentIdentity,
    ) -> None:
        """Test that medium quality (6.0-8.0) returns no strategy proposal."""
        snapshot = MagicMock(spec=AgentPerformanceSnapshot)
        snapshot.overall_quality_score = 7.5
        snapshot.agent_id = NotBlankStr("test-agent")

        context = EvolutionContext(
            agent_id=NotBlankStr("test-agent"),
            identity=mock_identity,
            performance_snapshot=snapshot,
            recent_task_results=(),
            recent_procedural_memories=(),
        )

        proposals = await proposer.propose(
            agent_id=context.agent_id,
            context=context,
        )

        # Should not suggest strategy for medium quality without memories
        strategy_proposals = [
            p for p in proposals if p.axis == AdaptationAxis.STRATEGY_SELECTION
        ]
        assert len(strategy_proposals) == 0

    @pytest.mark.asyncio
    async def test_propose_with_procedural_memories(
        self,
        proposer: SelfReportProposer,
        mock_identity: AgentIdentity,
    ) -> None:
        """Test that procedural memories trigger prompt template adaptation."""

        snapshot = MagicMock(spec=AgentPerformanceSnapshot)
        snapshot.overall_quality_score = 7.0
        snapshot.agent_id = NotBlankStr("test-agent")

        memory1 = MagicMock(spec=MemoryEntry)
        memory1.id = NotBlankStr("mem1")
        memory1.created_at = datetime.now(UTC)
        memory1.updated_at = None
        memory1.expires_at = None
        memory2 = MagicMock(spec=MemoryEntry)
        memory2.id = NotBlankStr("mem2")
        memory2.created_at = datetime.now(UTC)
        memory2.updated_at = None
        memory2.expires_at = None

        context = EvolutionContext(
            agent_id=NotBlankStr("test-agent"),
            identity=mock_identity,
            performance_snapshot=snapshot,
            recent_task_results=(),
            recent_procedural_memories=(memory1, memory2),
        )

        proposals = await proposer.propose(
            agent_id=context.agent_id,
            context=context,
        )

        # Should suggest prompt template adaptation when memories exist
        assert any(p.axis == AdaptationAxis.PROMPT_TEMPLATE for p in proposals)

    @pytest.mark.asyncio
    async def test_propose_never_identity_axis(
        self,
        proposer: SelfReportProposer,
        mock_identity: AgentIdentity,
    ) -> None:
        """Test that self-report never proposes identity axis."""

        snapshot = MagicMock(spec=AgentPerformanceSnapshot)
        snapshot.overall_quality_score = 9.5
        snapshot.agent_id = NotBlankStr("test-agent")

        memory = MagicMock(spec=MemoryEntry)
        memory.id = NotBlankStr("mem1")
        memory.created_at = datetime.now(UTC)
        memory.updated_at = None
        memory.expires_at = None

        context = EvolutionContext(
            agent_id=NotBlankStr("test-agent"),
            identity=mock_identity,
            performance_snapshot=snapshot,
            recent_task_results=(),
            recent_procedural_memories=(memory,),
        )

        proposals = await proposer.propose(
            agent_id=context.agent_id,
            context=context,
        )

        # Should never propose identity adaptations
        assert not any(p.axis == AdaptationAxis.IDENTITY for p in proposals)

    @pytest.mark.asyncio
    async def test_propose_all_proposals_success_source(
        self,
        proposer: SelfReportProposer,
        mock_identity: AgentIdentity,
    ) -> None:
        """Test that all proposals use SUCCESS source."""

        snapshot = MagicMock(spec=AgentPerformanceSnapshot)
        snapshot.overall_quality_score = 9.5
        snapshot.agent_id = NotBlankStr("test-agent")

        memory = MagicMock(spec=MemoryEntry)
        memory.id = NotBlankStr("mem1")
        memory.created_at = datetime.now(UTC)
        memory.updated_at = None
        memory.expires_at = None

        context = EvolutionContext(
            agent_id=NotBlankStr("test-agent"),
            identity=mock_identity,
            performance_snapshot=snapshot,
            recent_task_results=(),
            recent_procedural_memories=(memory,),
        )

        proposals = await proposer.propose(
            agent_id=context.agent_id,
            context=context,
        )

        # All proposals should use success source
        assert all(p.source == AdaptationSource.SUCCESS for p in proposals)

    @pytest.mark.asyncio
    async def test_propose_high_quality_and_memories(
        self,
        proposer: SelfReportProposer,
        mock_identity: AgentIdentity,
    ) -> None:
        """Test proposer with both high quality and memories."""

        snapshot = MagicMock(spec=AgentPerformanceSnapshot)
        snapshot.overall_quality_score = 9.5
        snapshot.agent_id = NotBlankStr("test-agent")

        memory1 = MagicMock(spec=MemoryEntry)
        memory1.id = NotBlankStr("mem1")
        memory1.created_at = datetime.now(UTC)
        memory1.updated_at = None
        memory1.expires_at = None
        memory2 = MagicMock(spec=MemoryEntry)
        memory2.id = NotBlankStr("mem2")
        memory2.created_at = datetime.now(UTC)
        memory2.updated_at = None
        memory2.expires_at = None

        context = EvolutionContext(
            agent_id=NotBlankStr("test-agent"),
            identity=mock_identity,
            performance_snapshot=snapshot,
            recent_task_results=(),
            recent_procedural_memories=(memory1, memory2),
        )

        proposals = await proposer.propose(
            agent_id=context.agent_id,
            context=context,
        )

        # Should have both strategy and prompt template proposals
        axes = {p.axis for p in proposals}
        assert AdaptationAxis.STRATEGY_SELECTION in axes
        assert AdaptationAxis.PROMPT_TEMPLATE in axes
        # Should never have identity
        assert AdaptationAxis.IDENTITY not in axes
