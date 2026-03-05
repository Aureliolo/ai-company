"""Tests for engine error hierarchy."""

import pytest

from ai_company.engine.errors import (
    EngineError,
    ExecutionStateError,
    MaxTurnsExceededError,
    PromptBuildError,
)


@pytest.mark.unit
class TestEngineErrorHierarchy:
    """Engine error hierarchy and inheritance."""

    def test_execution_state_error_is_engine_error(self) -> None:
        assert issubclass(ExecutionStateError, EngineError)
        err = ExecutionStateError("test")
        assert isinstance(err, EngineError)

    def test_max_turns_exceeded_error_is_engine_error(self) -> None:
        assert issubclass(MaxTurnsExceededError, EngineError)
        err = MaxTurnsExceededError("exceeded")
        assert isinstance(err, EngineError)
        assert str(err) == "exceeded"

    def test_prompt_build_error_is_engine_error(self) -> None:
        assert issubclass(PromptBuildError, EngineError)
