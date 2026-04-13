"""Tests for ToolDisclosureConfig."""

import pytest
from pydantic import ValidationError

from synthorg.tools.disclosure_config import ToolDisclosureConfig


@pytest.mark.unit
class TestToolDisclosureConfig:
    """Tests for ToolDisclosureConfig model."""

    def test_defaults(self) -> None:
        config = ToolDisclosureConfig()
        assert config.l1_token_budget == 3000
        assert config.l2_token_budget == 15000
        assert config.auto_unload_on_budget_pressure is True
        assert config.unload_threshold_percent == 80.0

    def test_custom_values(self) -> None:
        config = ToolDisclosureConfig(
            l1_token_budget=5000,
            l2_token_budget=30000,
            auto_unload_on_budget_pressure=False,
            unload_threshold_percent=90.0,
        )
        assert config.l1_token_budget == 5000
        assert config.l2_token_budget == 30000
        assert config.auto_unload_on_budget_pressure is False
        assert config.unload_threshold_percent == 90.0

    def test_frozen(self) -> None:
        config = ToolDisclosureConfig()
        with pytest.raises(ValidationError):
            config.l1_token_budget = 999  # type: ignore[misc]

    def test_l1_budget_min(self) -> None:
        config = ToolDisclosureConfig(l1_token_budget=500)
        assert config.l1_token_budget == 500

    def test_l1_budget_below_min_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ToolDisclosureConfig(l1_token_budget=499)

    def test_l1_budget_max(self) -> None:
        config = ToolDisclosureConfig(l1_token_budget=20000, l2_token_budget=20000)
        assert config.l1_token_budget == 20000

    def test_l1_budget_above_max_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ToolDisclosureConfig(l1_token_budget=20001)

    def test_l2_budget_min(self) -> None:
        config = ToolDisclosureConfig(l1_token_budget=500, l2_token_budget=1000)
        assert config.l2_token_budget == 1000

    def test_l2_budget_below_min_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ToolDisclosureConfig(l2_token_budget=999)

    def test_l2_budget_max(self) -> None:
        config = ToolDisclosureConfig(l2_token_budget=100000)
        assert config.l2_token_budget == 100000

    def test_l2_budget_above_max_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ToolDisclosureConfig(l2_token_budget=100001)

    def test_threshold_min(self) -> None:
        config = ToolDisclosureConfig(unload_threshold_percent=50.0)
        assert config.unload_threshold_percent == 50.0

    def test_threshold_below_min_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ToolDisclosureConfig(unload_threshold_percent=49.9)

    def test_threshold_max(self) -> None:
        config = ToolDisclosureConfig(unload_threshold_percent=99.0)
        assert config.unload_threshold_percent == 99.0

    def test_threshold_above_max_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ToolDisclosureConfig(unload_threshold_percent=99.1)

    def test_l2_less_than_l1_rejected(self) -> None:
        with pytest.raises(ValidationError, match="l2_token_budget"):
            ToolDisclosureConfig(l1_token_budget=5000, l2_token_budget=3000)

    def test_l2_equal_to_l1_accepted(self) -> None:
        config = ToolDisclosureConfig(
            l1_token_budget=5000,
            l2_token_budget=5000,
        )
        assert config.l1_token_budget == 5000
        assert config.l2_token_budget == 5000
