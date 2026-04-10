"""Tests for SuccessMemoryProposer."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from synthorg.memory.procedural.models import (
    ProceduralMemoryConfig,
    ProceduralMemoryProposal,
)
from synthorg.memory.procedural.success_proposer import SuccessMemoryProposer
from synthorg.providers.errors import ProviderError
from synthorg.providers.models import CompletionResponse

pytestmark = pytest.mark.unit


class TestSuccessMemoryProposer:
    """Tests for SuccessMemoryProposer."""

    @pytest.fixture
    def provider(self) -> AsyncMock:
        """Mock completion provider."""
        return AsyncMock()

    @pytest.fixture
    def config(self) -> ProceduralMemoryConfig:
        """Config for the proposer."""
        return ProceduralMemoryConfig(
            enabled=True,
            model="test-model",
            temperature=0.2,
            max_tokens=1500,
            min_confidence=0.6,
        )

    @pytest.fixture
    def proposer(
        self,
        provider: AsyncMock,
        config: ProceduralMemoryConfig,
    ) -> SuccessMemoryProposer:
        """Create a SuccessMemoryProposer."""
        return SuccessMemoryProposer(provider=provider, config=config)

    async def test_initialization(
        self,
        proposer: SuccessMemoryProposer,
        config: ProceduralMemoryConfig,
    ) -> None:
        """Test that proposer initializes with correct settings."""
        assert proposer._provider is not None
        assert proposer._config == config
        assert proposer._completion_config.temperature == 0.2
        assert proposer._completion_config.max_tokens == 1500

    async def test_propose_returns_proposal_on_success(
        self,
        proposer: SuccessMemoryProposer,
        provider: AsyncMock,
    ) -> None:
        """Test that propose returns a valid proposal on successful LLM call."""
        json_response = (
            '{"discovery": "Test discovery", '
            '"condition": "Test condition", '
            '"action": "Test action", '
            '"rationale": "Test rationale", '
            '"confidence": 0.85, '
            '"tags": ["test", "success"]}'
        )
        response = MagicMock(spec=CompletionResponse)
        response.content = json_response
        provider.complete = AsyncMock(return_value=response)

        execution_result = MagicMock()
        execution_result.turn_count = 3
        execution_result.tools_used = ["tool1", "tool2"]

        proposal = await proposer.propose(execution_result)

        assert proposal is not None
        assert isinstance(proposal, ProceduralMemoryProposal)
        assert proposal.discovery == "Test discovery"
        assert proposal.confidence == 0.85
        provider.complete.assert_called_once()

    async def test_propose_returns_none_on_low_confidence(
        self,
        proposer: SuccessMemoryProposer,
        provider: AsyncMock,
    ) -> None:
        """Test that propose returns None when confidence is below threshold."""
        json_response = (
            '{"discovery": "Test discovery", '
            '"condition": "Test condition", '
            '"action": "Test action", '
            '"rationale": "Test rationale", '
            '"confidence": 0.4, '
            '"tags": []}'
        )
        response = MagicMock(spec=CompletionResponse)
        response.content = json_response
        provider.complete = AsyncMock(return_value=response)

        execution_result = MagicMock()
        execution_result.turn_count = 2
        execution_result.tools_used = []

        proposal = await proposer.propose(execution_result)

        assert proposal is None
        provider.complete.assert_called_once()

    async def test_propose_returns_none_on_malformed_json(
        self,
        proposer: SuccessMemoryProposer,
        provider: AsyncMock,
    ) -> None:
        """Test that propose returns None on malformed JSON."""
        response = MagicMock(spec=CompletionResponse)
        response.content = "not valid json"
        provider.complete = AsyncMock(return_value=response)

        execution_result = MagicMock()
        execution_result.turn_count = 1
        execution_result.tools_used = []

        proposal = await proposer.propose(execution_result)

        assert proposal is None

    async def test_propose_returns_none_on_empty_response(
        self,
        proposer: SuccessMemoryProposer,
        provider: AsyncMock,
    ) -> None:
        """Test that propose returns None on empty response."""
        response = MagicMock(spec=CompletionResponse)
        response.content = ""
        provider.complete = AsyncMock(return_value=response)

        execution_result = MagicMock()
        execution_result.turn_count = 1
        execution_result.tools_used = []

        proposal = await proposer.propose(execution_result)

        assert proposal is None

    async def test_propose_returns_none_on_validation_error(
        self,
        proposer: SuccessMemoryProposer,
        provider: AsyncMock,
    ) -> None:
        """Test that propose returns None when proposal validation fails."""
        # Missing required fields
        json_response = '{"discovery": "Test discovery"}'
        response = MagicMock(spec=CompletionResponse)
        response.content = json_response
        provider.complete = AsyncMock(return_value=response)

        execution_result = MagicMock()
        execution_result.turn_count = 1
        execution_result.tools_used = []

        proposal = await proposer.propose(execution_result)

        assert proposal is None

    async def test_propose_propagates_non_retryable_error(
        self,
        proposer: SuccessMemoryProposer,
        provider: AsyncMock,
    ) -> None:
        """Test that non-retryable provider errors propagate."""
        error = ProviderError("Invalid API key")
        error.is_retryable = False
        provider.complete = AsyncMock(side_effect=error)

        execution_result = MagicMock()
        execution_result.turn_count = 1
        execution_result.tools_used = []

        with pytest.raises(ProviderError):
            await proposer.propose(execution_result)

    async def test_propose_returns_none_on_retryable_error(
        self,
        proposer: SuccessMemoryProposer,
        provider: AsyncMock,
    ) -> None:
        """Test that retryable provider errors return None."""
        error = ProviderError("Rate limited")
        error.is_retryable = True
        provider.complete = AsyncMock(side_effect=error)

        execution_result = MagicMock()
        execution_result.turn_count = 1
        execution_result.tools_used = []

        proposal = await proposer.propose(execution_result)

        assert proposal is None

    async def test_propose_handles_markdown_fenced_json(
        self,
        proposer: SuccessMemoryProposer,
        provider: AsyncMock,
    ) -> None:
        """Test that propose handles JSON in markdown fences."""
        json_response = (
            "```json\n"
            '{"discovery": "Test discovery", '
            '"condition": "Test condition", '
            '"action": "Test action", '
            '"rationale": "Test rationale", '
            '"confidence": 0.9, '
            '"tags": []}'
            "\n```"
        )
        response = MagicMock(spec=CompletionResponse)
        response.content = json_response
        provider.complete = AsyncMock(return_value=response)

        execution_result = MagicMock()
        execution_result.turn_count = 3
        execution_result.tools_used = ["tool1"]

        proposal = await proposer.propose(execution_result)

        assert proposal is not None
        assert proposal.confidence == 0.9

    async def test_propose_with_execution_steps(
        self,
        proposer: SuccessMemoryProposer,
        provider: AsyncMock,
    ) -> None:
        """Test that propose correctly parses execution_steps."""
        json_response = (
            '{"discovery": "Test discovery", '
            '"condition": "Test condition", '
            '"action": "Test action", '
            '"rationale": "Test rationale", '
            '"execution_steps": ["Step 1", "Step 2", "Step 3"], '
            '"confidence": 0.88, '
            '"tags": ["multi-step"]}'
        )
        response = MagicMock(spec=CompletionResponse)
        response.content = json_response
        provider.complete = AsyncMock(return_value=response)

        execution_result = MagicMock()
        execution_result.turn_count = 4
        execution_result.tools_used = ["tool1", "tool2"]

        proposal = await proposer.propose(execution_result)

        assert proposal is not None
        assert len(proposal.execution_steps) == 3
        assert proposal.execution_steps[0] == "Step 1"
