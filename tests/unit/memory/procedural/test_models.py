"""Tests for procedural memory domain models."""

import pytest
from pydantic import ValidationError

from synthorg.core.enums import TaskType
from synthorg.memory.procedural.models import (
    FailureAnalysisPayload,
    ProceduralMemoryConfig,
    ProceduralMemoryProposal,
)


def _make_payload(**overrides: object) -> FailureAnalysisPayload:
    """Build a valid FailureAnalysisPayload with overridable defaults."""
    defaults: dict[str, object] = {
        "task_id": "task-001",
        "task_title": "Implement auth module",
        "task_description": "Create JWT authentication.",
        "task_type": TaskType.DEVELOPMENT,
        "error_message": "LLM timeout after 30s",
        "strategy_type": "fail_reassign",
        "termination_reason": "error",
        "turn_count": 5,
        "tool_calls_made": ("code_search", "run_tests"),
        "retry_count": 0,
        "max_retries": 2,
        "can_reassign": True,
    }
    defaults.update(overrides)
    return FailureAnalysisPayload(**defaults)


def _make_proposal(**overrides: object) -> ProceduralMemoryProposal:
    """Build a valid ProceduralMemoryProposal with overridable defaults."""
    defaults: dict[str, object] = {
        "discovery": "When facing LLM timeouts, break task into smaller steps.",
        "condition": "Task exceeds 10 turns without progress.",
        "action": "Decompose the task into subtasks before retrying.",
        "rationale": "Smaller tasks reduce context window pressure.",
        "confidence": 0.85,
        "tags": ("timeout", "decomposition"),
    }
    defaults.update(overrides)
    return ProceduralMemoryProposal(**defaults)


# -- FailureAnalysisPayload -------------------------------------------


@pytest.mark.unit
class TestFailureAnalysisPayload:
    def test_happy_path(self) -> None:
        p = _make_payload()
        assert p.task_id == "task-001"
        assert p.task_type is TaskType.DEVELOPMENT
        assert p.turn_count == 5
        assert p.tool_calls_made == ("code_search", "run_tests")
        assert p.can_reassign is True

    def test_frozen(self) -> None:
        p = _make_payload()
        with pytest.raises(ValidationError):
            p.task_id = "other"  # type: ignore[misc]

    def test_empty_task_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_payload(task_id="")

    def test_whitespace_task_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_payload(task_id="   ")

    def test_negative_turn_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_payload(turn_count=-1)

    def test_zero_turn_count_accepted(self) -> None:
        p = _make_payload(turn_count=0)
        assert p.turn_count == 0

    def test_negative_retry_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_payload(retry_count=-1)

    def test_negative_max_retries_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_payload(max_retries=-1)

    def test_empty_tool_calls_accepted(self) -> None:
        p = _make_payload(tool_calls_made=())
        assert p.tool_calls_made == ()

    def test_nan_turn_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_payload(turn_count=float("nan"))


# -- ProceduralMemoryProposal -----------------------------------------


@pytest.mark.unit
class TestProceduralMemoryProposal:
    def test_happy_path(self) -> None:
        p = _make_proposal()
        assert p.discovery.startswith("When facing")
        assert p.confidence == 0.85
        assert p.tags == ("timeout", "decomposition")

    def test_frozen(self) -> None:
        p = _make_proposal()
        with pytest.raises(ValidationError):
            p.confidence = 0.5  # type: ignore[misc]

    def test_empty_discovery_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_proposal(discovery="")

    def test_whitespace_condition_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_proposal(condition="   ")

    def test_confidence_lower_bound(self) -> None:
        p = _make_proposal(confidence=0.0)
        assert p.confidence == 0.0

    def test_confidence_upper_bound(self) -> None:
        p = _make_proposal(confidence=1.0)
        assert p.confidence == 1.0

    def test_confidence_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_proposal(confidence=-0.1)

    def test_confidence_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_proposal(confidence=1.1)

    def test_confidence_nan_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_proposal(confidence=float("nan"))

    def test_default_tags_empty(self) -> None:
        p = _make_proposal(tags=())
        assert p.tags == ()

    def test_duplicate_tags_deduplicated(self) -> None:
        p = _make_proposal(tags=("api", "api", "timeout"))
        assert p.tags == ("api", "timeout")


# -- ProceduralMemoryConfig --------------------------------------------


@pytest.mark.unit
class TestProceduralMemoryConfig:
    def test_defaults(self) -> None:
        c = ProceduralMemoryConfig()
        assert c.enabled is True
        assert c.model == "example-small-001"
        assert c.temperature == 0.3
        assert c.max_tokens == 1000
        assert c.min_confidence == 0.5

    def test_frozen(self) -> None:
        c = ProceduralMemoryConfig()
        with pytest.raises(ValidationError):
            c.enabled = False  # type: ignore[misc]

    def test_custom_model(self) -> None:
        c = ProceduralMemoryConfig(model="test-provider/test-large-001")
        assert c.model == "test-provider/test-large-001"

    def test_empty_model_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ProceduralMemoryConfig(model="")

    def test_temperature_bounds(self) -> None:
        assert ProceduralMemoryConfig(temperature=0.0).temperature == 0.0
        assert ProceduralMemoryConfig(temperature=2.0).temperature == 2.0

    def test_temperature_below_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ProceduralMemoryConfig(temperature=-0.1)

    def test_temperature_above_two_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ProceduralMemoryConfig(temperature=2.1)

    def test_max_tokens_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ProceduralMemoryConfig(max_tokens=0)

    def test_min_confidence_bounds(self) -> None:
        assert ProceduralMemoryConfig(min_confidence=0.0).min_confidence == 0.0
        assert ProceduralMemoryConfig(min_confidence=1.0).min_confidence == 1.0

    def test_min_confidence_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ProceduralMemoryConfig(min_confidence=1.1)

    def test_disabled(self) -> None:
        c = ProceduralMemoryConfig(enabled=False)
        assert c.enabled is False
