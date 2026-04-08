"""Tests for analytics tool configuration models."""

import pytest
from pydantic import ValidationError

from synthorg.tools.analytics.config import AnalyticsToolsConfig


@pytest.mark.unit
class TestAnalyticsToolsConfig:
    """Tests for AnalyticsToolsConfig."""

    def test_default_values(self) -> None:
        config = AnalyticsToolsConfig()
        assert config.query_timeout == 60.0
        assert config.max_rows == 10_000
        assert config.allowed_metrics is None

    def test_frozen(self) -> None:
        config = AnalyticsToolsConfig()
        with pytest.raises(ValidationError):
            config.query_timeout = 30.0  # type: ignore[misc]

    def test_custom_values(self) -> None:
        config = AnalyticsToolsConfig(
            query_timeout=120.0,
            max_rows=5000,
            allowed_metrics=frozenset({"total_cost", "task_count"}),
        )
        assert config.query_timeout == 120.0
        assert config.max_rows == 5000
        assert config.allowed_metrics == frozenset({"total_cost", "task_count"})

    def test_query_timeout_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            AnalyticsToolsConfig(query_timeout=0)

    def test_query_timeout_max(self) -> None:
        with pytest.raises(ValidationError):
            AnalyticsToolsConfig(query_timeout=301.0)

    def test_max_rows_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            AnalyticsToolsConfig(max_rows=0)

    def test_max_rows_upper_bound(self) -> None:
        with pytest.raises(ValidationError):
            AnalyticsToolsConfig(max_rows=100_001)

    def test_rejects_nan(self) -> None:
        with pytest.raises(ValidationError):
            AnalyticsToolsConfig(query_timeout=float("nan"))

    def test_rejects_inf(self) -> None:
        with pytest.raises(ValidationError):
            AnalyticsToolsConfig(query_timeout=float("inf"))

    def test_blank_metric_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AnalyticsToolsConfig(allowed_metrics=frozenset({"valid", "  "}))
