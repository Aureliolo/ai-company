"""Tests for Hybrid loop configuration models."""

import pytest
from pydantic import ValidationError

from synthorg.engine.hybrid_models import HybridLoopConfig


@pytest.mark.unit
class TestHybridLoopConfigDefaults:
    """Verify default values and basic construction."""

    def test_defaults(self) -> None:
        cfg = HybridLoopConfig()

        assert cfg.planner_model is None
        assert cfg.executor_model is None
        assert cfg.max_plan_steps == 7
        assert cfg.max_turns_per_step == 5
        assert cfg.max_replans == 3
        assert cfg.checkpoint_after_each_step is True
        assert cfg.allow_replan_on_completion is True

    def test_custom_values(self) -> None:
        cfg = HybridLoopConfig(
            planner_model="test-large-001",
            executor_model="test-small-001",
            max_plan_steps=10,
            max_turns_per_step=8,
            max_replans=5,
            checkpoint_after_each_step=False,
            allow_replan_on_completion=False,
        )

        assert cfg.planner_model == "test-large-001"
        assert cfg.executor_model == "test-small-001"
        assert cfg.max_plan_steps == 10
        assert cfg.max_turns_per_step == 8
        assert cfg.max_replans == 5
        assert cfg.checkpoint_after_each_step is False
        assert cfg.allow_replan_on_completion is False


@pytest.mark.unit
class TestHybridLoopConfigFrozen:
    """Verify immutability."""

    def test_frozen(self) -> None:
        cfg = HybridLoopConfig()

        with pytest.raises(ValidationError):
            cfg.max_plan_steps = 10  # type: ignore[misc]

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError, match="extra"):
            HybridLoopConfig(unknown_field="value")  # type: ignore[call-arg]


@pytest.mark.unit
class TestHybridLoopConfigValidation:
    """Verify field constraints."""

    @pytest.mark.parametrize(
        ("field", "bad_value"),
        [
            ("max_plan_steps", 0),
            ("max_plan_steps", -1),
            ("max_plan_steps", 21),
            ("max_turns_per_step", 0),
            ("max_turns_per_step", -1),
            ("max_turns_per_step", 51),
            ("max_replans", -1),
            ("max_replans", 11),
        ],
    )
    def test_range_violations(self, field: str, bad_value: int) -> None:
        with pytest.raises(ValidationError):
            HybridLoopConfig(**{field: bad_value})  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        ("field", "good_value"),
        [
            ("max_plan_steps", 1),
            ("max_plan_steps", 20),
            ("max_turns_per_step", 1),
            ("max_turns_per_step", 50),
            ("max_replans", 0),
            ("max_replans", 10),
        ],
    )
    def test_range_boundaries_accepted(self, field: str, good_value: int) -> None:
        cfg = HybridLoopConfig(**{field: good_value})  # type: ignore[arg-type]
        assert getattr(cfg, field) == good_value

    def test_blank_planner_model_rejected(self) -> None:
        with pytest.raises(ValidationError):
            HybridLoopConfig(planner_model="   ")

    def test_blank_executor_model_rejected(self) -> None:
        with pytest.raises(ValidationError):
            HybridLoopConfig(executor_model="")
