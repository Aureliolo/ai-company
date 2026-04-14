"""Tests for SemanticDriftDetector middleware."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from synthorg.engine.middleware.semantic_drift import (
    SemanticDriftConfig,
    SemanticDriftDetector,
)


def _make_ctx(
    acceptance_criteria: str | None = "Task must produce a summary",
) -> MagicMock:
    """Create a mock AgentMiddlewareContext with task criteria."""
    ctx = MagicMock()
    ctx.agent_id = "agent-001"
    ctx.task_id = "task-001"
    ctx.execution_id = "exec-001"
    ctx.metadata = {}
    ctx.with_metadata = MagicMock(side_effect=lambda k, v: ctx)
    task = MagicMock()
    task.acceptance_criteria = acceptance_criteria
    ctx.task = task
    return ctx


def _make_model_result(text: str = "Here is a summary") -> MagicMock:
    """Create a mock ModelCallResult."""
    result = MagicMock()
    result.response_text = text
    return result


@pytest.mark.unit
class TestSemanticDriftConfig:
    """Tests for SemanticDriftConfig defaults and validation."""

    def test_defaults(self) -> None:
        config = SemanticDriftConfig()
        assert config.enabled is False
        assert config.threshold == pytest.approx(0.35)
        assert config.embedding_model is None

    def test_frozen(self) -> None:
        from pydantic import ValidationError

        config = SemanticDriftConfig()
        with pytest.raises(ValidationError):
            config.enabled = True  # type: ignore[misc]

    def test_threshold_bounds(self) -> None:
        with pytest.raises(ValueError, match="greater than or equal to 0"):
            SemanticDriftConfig(threshold=-0.1)
        with pytest.raises(ValueError, match="less than or equal to 1"):
            SemanticDriftConfig(threshold=1.5)

    def test_custom_threshold(self) -> None:
        config = SemanticDriftConfig(enabled=True, threshold=0.5)
        assert config.enabled is True
        assert config.threshold == pytest.approx(0.5)


@pytest.mark.unit
class TestSemanticDriftDetector:
    """Tests for SemanticDriftDetector middleware."""

    async def test_name_property(self) -> None:
        config = SemanticDriftConfig(enabled=True)
        detector = SemanticDriftDetector(config=config)
        assert detector.name == "semantic_drift_detector"

    async def test_disabled_passes_through(self) -> None:
        """When disabled, middleware passes through unchanged."""
        config = SemanticDriftConfig(enabled=False)
        detector = SemanticDriftDetector(config=config)

        ctx = _make_ctx()
        expected = _make_model_result()
        call = AsyncMock(return_value=expected)

        result = await detector.wrap_model_call(ctx, call)
        assert result == expected
        call.assert_awaited_once_with(ctx)

    async def test_no_acceptance_criteria_passes_through(self) -> None:
        """When acceptance_criteria is None, skip with no error."""
        config = SemanticDriftConfig(enabled=True)
        detector = SemanticDriftDetector(config=config)

        ctx = _make_ctx(acceptance_criteria=None)
        expected = _make_model_result()
        call = AsyncMock(return_value=expected)

        result = await detector.wrap_model_call(ctx, call)
        assert result == expected

    async def test_drift_detected_annotates_metadata(self) -> None:
        """When similarity is below threshold, metadata is annotated."""
        config = SemanticDriftConfig(enabled=True, threshold=0.99)
        # Mock embedding function to return orthogonal vectors.
        detector = SemanticDriftDetector(config=config)
        detector._compute_similarity = AsyncMock(return_value=0.1)  # type: ignore[method-assign]

        ctx = _make_ctx()
        expected = _make_model_result()
        call = AsyncMock(return_value=expected)

        result = await detector.wrap_model_call(ctx, call)
        assert result == expected
        # Metadata should have been annotated.
        ctx.with_metadata.assert_called_once_with(
            "semantic_drift_score",
            0.1,
        )

    async def test_no_drift_no_annotation(self) -> None:
        """When similarity is above threshold, no annotation."""
        config = SemanticDriftConfig(enabled=True, threshold=0.1)
        detector = SemanticDriftDetector(config=config)
        detector._compute_similarity = AsyncMock(return_value=0.9)  # type: ignore[method-assign]

        ctx = _make_ctx()
        expected = _make_model_result()
        call = AsyncMock(return_value=expected)

        result = await detector.wrap_model_call(ctx, call)
        assert result == expected
        # with_metadata should NOT have been called for drift.
        ctx.with_metadata.assert_not_called()

    async def test_embedding_error_fails_soft(self) -> None:
        """Embedding errors should not propagate -- fail soft."""
        config = SemanticDriftConfig(enabled=True)
        detector = SemanticDriftDetector(config=config)
        detector._compute_similarity = AsyncMock(  # type: ignore[method-assign]
            side_effect=RuntimeError("embedding failed"),
        )

        ctx = _make_ctx()
        expected = _make_model_result()
        call = AsyncMock(return_value=expected)

        result = await detector.wrap_model_call(ctx, call)
        # Should still return result, not raise.
        assert result == expected

    async def test_always_calls_inner(self) -> None:
        """Inner call is always made, even when drift detected."""
        config = SemanticDriftConfig(enabled=True, threshold=0.99)
        detector = SemanticDriftDetector(config=config)
        detector._compute_similarity = AsyncMock(return_value=0.01)  # type: ignore[method-assign]

        ctx = _make_ctx()
        expected = _make_model_result()
        call = AsyncMock(return_value=expected)

        await detector.wrap_model_call(ctx, call)
        call.assert_awaited_once_with(ctx)


@pytest.mark.unit
class TestSemanticDriftProperties:
    """Property-based tests for SemanticDriftDetector."""

    @given(
        threshold=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    )
    @settings(max_examples=50)
    def test_config_accepts_valid_threshold(self, threshold: float) -> None:
        config = SemanticDriftConfig(threshold=threshold)
        assert 0.0 <= config.threshold <= 1.0
