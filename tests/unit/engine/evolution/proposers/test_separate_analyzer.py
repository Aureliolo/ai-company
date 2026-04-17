"""Tests for the SeparateAnalyzerProposer."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from synthorg.core.agent import AgentIdentity
from synthorg.core.types import NotBlankStr
from synthorg.engine.evolution.models import (
    AdaptationAxis,
)
from synthorg.engine.evolution.proposers.separate_analyzer import (
    SeparateAnalyzerProposer,
)
from synthorg.engine.evolution.protocols import EvolutionContext
from synthorg.hr.performance.models import (
    AgentPerformanceSnapshot,
)
from synthorg.providers.enums import FinishReason
from synthorg.providers.models import (
    CompletionResponse,
    TokenUsage,
)


@pytest.mark.unit
class TestSeparateAnalyzerProposer:
    """Test suite for SeparateAnalyzerProposer."""

    @pytest.fixture
    def mock_provider(self) -> AsyncMock:
        """Create a mock completion provider."""
        provider = AsyncMock()
        provider.complete = AsyncMock()
        return provider

    @pytest.fixture
    def proposer(self, mock_provider: AsyncMock) -> SeparateAnalyzerProposer:
        """Create a SeparateAnalyzerProposer instance."""
        return SeparateAnalyzerProposer(
            mock_provider,
            model="test-model",
            temperature=0.3,
            max_tokens=2000,
        )

    @pytest.fixture
    def mock_identity(self) -> AgentIdentity:
        """Create a mock agent identity."""
        identity = MagicMock(spec=AgentIdentity)
        identity.name = NotBlankStr("test-agent")
        identity.level = "junior"
        identity.role = "test_role"
        identity.autonomy_level = None
        return identity

    @pytest.fixture
    def mock_performance_snapshot(self) -> AgentPerformanceSnapshot:
        """Create a mock performance snapshot."""
        snapshot = MagicMock(spec=AgentPerformanceSnapshot)
        snapshot.overall_quality_score = 7.5
        snapshot.overall_collaboration_score = 8.0
        return snapshot

    @pytest.fixture
    def evolution_context(
        self,
        mock_identity: AgentIdentity,
        mock_performance_snapshot: AgentPerformanceSnapshot,
    ) -> EvolutionContext:
        """Create an evolution context for testing."""
        return EvolutionContext(
            agent_id=NotBlankStr("test-agent"),
            identity=mock_identity,
            performance_snapshot=mock_performance_snapshot,
            recent_task_results=(),
            recent_procedural_memories=(),
        )

    @pytest.mark.asyncio
    async def test_name_property(self, proposer: SeparateAnalyzerProposer) -> None:
        """Test that the proposer returns correct name."""
        assert proposer.name == "separate_analyzer"

    @pytest.mark.asyncio
    async def test_propose_calls_provider(
        self,
        proposer: SeparateAnalyzerProposer,
        mock_provider: AsyncMock,
        evolution_context: EvolutionContext,
    ) -> None:
        """Test that propose calls the completion provider."""
        response_data = {
            "proposals": [
                {
                    "axis": "prompt_template",
                    "description": "Test adaptation",
                    "changes": {"template": "new template"},
                    "confidence": 0.8,
                    "source": "success",
                }
            ]
        }
        mock_provider.complete.return_value = CompletionResponse(
            content=json.dumps(response_data),
            finish_reason=FinishReason.STOP,
            usage=TokenUsage(
                input_tokens=100,
                output_tokens=50,
                cost=0.01,
            ),
            model=NotBlankStr("test-model"),
        )

        proposals = await proposer.propose(
            agent_id=evolution_context.agent_id,
            context=evolution_context,
        )

        assert len(proposals) == 1
        assert proposals[0].axis == AdaptationAxis.PROMPT_TEMPLATE
        assert proposals[0].description == "Test adaptation"
        assert proposals[0].confidence == 0.8
        mock_provider.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_propose_handles_empty_response(
        self,
        proposer: SeparateAnalyzerProposer,
        mock_provider: AsyncMock,
        evolution_context: EvolutionContext,
    ) -> None:
        """Test that empty or None content returns empty tuple."""
        mock_provider.complete.return_value = CompletionResponse(
            content="",
            finish_reason=FinishReason.STOP,
            usage=TokenUsage(
                input_tokens=100,
                output_tokens=0,
                cost=0.01,
            ),
            model=NotBlankStr("test-model"),
        )

        proposals = await proposer.propose(
            agent_id=evolution_context.agent_id,
            context=evolution_context,
        )

        assert proposals == ()

    @pytest.mark.asyncio
    async def test_propose_handles_malformed_json(
        self,
        proposer: SeparateAnalyzerProposer,
        mock_provider: AsyncMock,
        evolution_context: EvolutionContext,
    ) -> None:
        """Test that malformed JSON returns empty tuple."""
        mock_provider.complete.return_value = CompletionResponse(
            content="not valid json {[]}",
            finish_reason=FinishReason.STOP,
            usage=TokenUsage(
                input_tokens=100,
                output_tokens=50,
                cost=0.01,
            ),
            model=NotBlankStr("test-model"),
        )

        proposals = await proposer.propose(
            agent_id=evolution_context.agent_id,
            context=evolution_context,
        )

        assert proposals == ()

    @pytest.mark.asyncio
    async def test_propose_handles_invalid_proposal_data(
        self,
        proposer: SeparateAnalyzerProposer,
        mock_provider: AsyncMock,
        evolution_context: EvolutionContext,
    ) -> None:
        """Test that invalid proposal data returns empty tuple."""
        response_data = {
            "proposals": [
                {
                    "axis": "invalid_axis",
                    "description": "",  # Empty description
                    "confidence": 2.0,  # Out of range
                }
            ]
        }
        mock_provider.complete.return_value = CompletionResponse(
            content=json.dumps(response_data),
            finish_reason=FinishReason.STOP,
            usage=TokenUsage(
                input_tokens=100,
                output_tokens=50,
                cost=0.01,
            ),
            model=NotBlankStr("test-model"),
        )

        proposals = await proposer.propose(
            agent_id=evolution_context.agent_id,
            context=evolution_context,
        )

        assert proposals == ()

    @pytest.mark.asyncio
    async def test_propose_handles_missing_proposals_key(
        self,
        proposer: SeparateAnalyzerProposer,
        mock_provider: AsyncMock,
        evolution_context: EvolutionContext,
    ) -> None:
        """Test that missing 'proposals' key returns empty tuple."""
        response_data = {"result": "no proposals"}
        mock_provider.complete.return_value = CompletionResponse(
            content=json.dumps(response_data),
            finish_reason=FinishReason.STOP,
            usage=TokenUsage(
                input_tokens=100,
                output_tokens=50,
                cost=0.01,
            ),
            model=NotBlankStr("test-model"),
        )

        proposals = await proposer.propose(
            agent_id=evolution_context.agent_id,
            context=evolution_context,
        )

        assert proposals == ()

    @pytest.mark.asyncio
    async def test_propose_multiple_proposals(
        self,
        proposer: SeparateAnalyzerProposer,
        mock_provider: AsyncMock,
        evolution_context: EvolutionContext,
    ) -> None:
        """Test parsing multiple proposals from response."""
        response_data = {
            "proposals": [
                {
                    "axis": "prompt_template",
                    "description": "First adaptation",
                    "changes": {"template": "new template 1"},
                    "confidence": 0.8,
                    "source": "success",
                },
                {
                    "axis": "strategy_selection",
                    "description": "Second adaptation",
                    "changes": {"strategy": "new_strategy"},
                    "confidence": 0.6,
                    "source": "failure",
                },
            ]
        }
        mock_provider.complete.return_value = CompletionResponse(
            content=json.dumps(response_data),
            finish_reason=FinishReason.STOP,
            usage=TokenUsage(
                input_tokens=100,
                output_tokens=100,
                cost=0.02,
            ),
            model=NotBlankStr("test-model"),
        )

        proposals = await proposer.propose(
            agent_id=evolution_context.agent_id,
            context=evolution_context,
        )

        assert len(proposals) == 2
        assert proposals[0].axis == AdaptationAxis.PROMPT_TEMPLATE
        assert proposals[1].axis == AdaptationAxis.STRATEGY_SELECTION
        assert proposals[0].confidence == 0.8
        assert proposals[1].confidence == 0.6

    @pytest.mark.asyncio
    async def test_propose_with_changes_payload(
        self,
        proposer: SeparateAnalyzerProposer,
        mock_provider: AsyncMock,
        evolution_context: EvolutionContext,
    ) -> None:
        """Test that changes payload is preserved."""
        changes_payload = {
            "template": "new prompt",
            "injected_memories": ["mem1", "mem2"],
        }
        response_data = {
            "proposals": [
                {
                    "axis": "prompt_template",
                    "description": "Test adaptation",
                    "changes": changes_payload,
                    "confidence": 0.9,
                    "source": "success",
                }
            ]
        }
        mock_provider.complete.return_value = CompletionResponse(
            content=json.dumps(response_data),
            finish_reason=FinishReason.STOP,
            usage=TokenUsage(
                input_tokens=100,
                output_tokens=50,
                cost=0.01,
            ),
            model=NotBlankStr("test-model"),
        )

        proposals = await proposer.propose(
            agent_id=evolution_context.agent_id,
            context=evolution_context,
        )

        assert len(proposals) == 1
        assert proposals[0].changes == changes_payload
