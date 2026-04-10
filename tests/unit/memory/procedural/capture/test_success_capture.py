"""Tests for SuccessCaptureStrategy."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.engine.loop_protocol import ExecutionResult, TerminationReason
from synthorg.engine.recovery import RecoveryResult
from synthorg.memory.procedural.capture.success_capture import SuccessCaptureStrategy
from synthorg.memory.procedural.models import (
    ProceduralMemoryConfig,
    ProceduralMemoryProposal,
)


@pytest.mark.unit
class TestSuccessCaptureStrategy:
    """Tests for SuccessCaptureStrategy."""

    @pytest.fixture
    def success_proposer(self):
        """Mock success proposer."""
        return AsyncMock()

    @pytest.fixture
    def memory_backend(self):
        """Mock memory backend."""
        return AsyncMock()

    @pytest.fixture
    def config(self):
        """Config for the success proposer."""
        return ProceduralMemoryConfig(
            enabled=True,
            model="test-model",
            temperature=0.3,
            max_tokens=1500,
            min_confidence=0.5,
        )

    @pytest.fixture
    def strategy(self, success_proposer, config):
        """Create a SuccessCaptureStrategy."""
        return SuccessCaptureStrategy(
            proposer=success_proposer,
            config=config,
            min_quality_score=8.0,
        )

    @pytest.fixture
    def execution_result_success(self):
        """Mock execution result with success termination."""
        result = MagicMock(spec=ExecutionResult)
        result.turns = []
        result.termination_reason = TerminationReason.COMPLETED
        return result

    @pytest.fixture
    def execution_result_failure(self):
        """Mock execution result with failure termination."""
        result = MagicMock(spec=ExecutionResult)
        result.turns = []
        result.termination_reason = TerminationReason.ERROR
        return result

    @pytest.fixture
    def recovery_result(self):
        """Mock recovery result."""
        result = MagicMock(spec=RecoveryResult)
        result.error_message = "Test error"
        return result

    async def test_name_property(self, strategy):
        """Test that name property returns expected value."""
        assert strategy.name == "success"

    async def test_capture_returns_none_on_failure(
        self,
        strategy,
        execution_result_failure,
        memory_backend,
        recovery_result,
    ):
        """Test that capture returns None when execution fails."""
        result = await strategy.capture(
            execution_result=execution_result_failure,
            recovery_result=recovery_result,
            agent_id=NotBlankStr("agent-1"),
            task_id=NotBlankStr("task-1"),
            memory_backend=memory_backend,
        )
        assert result is None

    async def test_capture_returns_none_on_success_with_low_quality(
        self,
        strategy,
        success_proposer,
        execution_result_success,
        memory_backend,
    ):
        """Test that capture returns None when quality is below threshold."""
        # Quality score too low (below min_quality_score=8.0)
        proposal = ProceduralMemoryProposal(
            discovery="Test discovery",
            condition="Test condition",
            action="Test action",
            rationale="Test rationale",
            confidence=0.6,  # Will result in quality < 8.0
            tags=("test",),
        )
        success_proposer.propose = AsyncMock(return_value=proposal)

        result = await strategy.capture(
            execution_result=execution_result_success,
            recovery_result=None,
            agent_id=NotBlankStr("agent-1"),
            task_id=NotBlankStr("task-1"),
            memory_backend=memory_backend,
        )

        assert result is None
        memory_backend.store.assert_not_called()

    async def test_capture_stores_on_success_with_high_quality(
        self,
        strategy,
        success_proposer,
        execution_result_success,
        memory_backend,
    ):
        """Test that capture stores memory when success and quality is high."""
        proposal = ProceduralMemoryProposal(
            discovery="Test discovery",
            condition="Test condition",
            action="Test action",
            rationale="Test rationale",
            confidence=0.9,  # Will result in quality >= 8.0
            tags=("test",),
        )
        success_proposer.propose = AsyncMock(return_value=proposal)
        memory_id = NotBlankStr("mem-456")
        memory_backend.store = AsyncMock(return_value=memory_id)

        result = await strategy.capture(
            execution_result=execution_result_success,
            recovery_result=None,
            agent_id=NotBlankStr("agent-1"),
            task_id=NotBlankStr("task-1"),
            memory_backend=memory_backend,
        )

        assert result == memory_id
        memory_backend.store.assert_called_once()

    async def test_capture_stores_with_success_derived_tag(
        self,
        strategy,
        success_proposer,
        execution_result_success,
        memory_backend,
    ):
        """Test that success-derived tag is added to stored memory."""
        proposal = ProceduralMemoryProposal(
            discovery="Test discovery",
            condition="Test condition",
            action="Test action",
            rationale="Test rationale",
            confidence=0.95,
            tags=("existing-tag",),
        )
        success_proposer.propose = AsyncMock(return_value=proposal)
        memory_id = NotBlankStr("mem-789")
        memory_backend.store = AsyncMock(return_value=memory_id)

        await strategy.capture(
            execution_result=execution_result_success,
            recovery_result=None,
            agent_id=NotBlankStr("agent-1"),
            task_id=NotBlankStr("task-1"),
            memory_backend=memory_backend,
        )

        # Check that store was called and the request includes success-derived tag
        memory_backend.store.assert_called_once()
        call_args = memory_backend.store.call_args
        store_request = call_args[0][1]
        assert "success-derived" in store_request.metadata.tags

    async def test_capture_returns_none_when_proposer_returns_none(
        self,
        strategy,
        success_proposer,
        execution_result_success,
        memory_backend,
    ):
        """Test that capture returns None when proposer returns None."""
        success_proposer.propose = AsyncMock(return_value=None)

        result = await strategy.capture(
            execution_result=execution_result_success,
            recovery_result=None,
            agent_id=NotBlankStr("agent-1"),
            task_id=NotBlankStr("task-1"),
            memory_backend=memory_backend,
        )

        assert result is None
        memory_backend.store.assert_not_called()
