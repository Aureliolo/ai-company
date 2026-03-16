"""Unit tests for config bridge."""

import pytest
from pydantic import BaseModel, ConfigDict

from synthorg.settings.config_bridge import extract_from_config


class _InnerConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    daily_limit: float = 10.0
    enabled: bool = True


class _FakeConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    company_name: str = "TestCo"
    budget: _InnerConfig = _InnerConfig()
    optional_field: str | None = None


@pytest.mark.unit
@pytest.mark.timeout(30)
class TestExtractFromConfig:
    """Tests for dotted-path config extraction."""

    def test_top_level_field(self) -> None:
        config = _FakeConfig()
        assert extract_from_config(config, "company_name") == "TestCo"

    def test_nested_field(self) -> None:
        config = _FakeConfig()
        assert extract_from_config(config, "budget.daily_limit") == "10.0"

    def test_nested_bool(self) -> None:
        config = _FakeConfig()
        assert extract_from_config(config, "budget.enabled") == "True"

    def test_missing_top_level(self) -> None:
        config = _FakeConfig()
        assert extract_from_config(config, "nonexistent") is None

    def test_missing_nested(self) -> None:
        config = _FakeConfig()
        assert extract_from_config(config, "budget.nonexistent") is None

    def test_none_field(self) -> None:
        config = _FakeConfig()
        assert extract_from_config(config, "optional_field") is None

    def test_empty_path(self) -> None:
        config = _FakeConfig()
        # Empty string splits to [''] — getattr('') fails
        assert extract_from_config(config, "") is None
