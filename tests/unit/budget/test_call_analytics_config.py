"""Tests for CallAnalyticsConfig and RetryAlertConfig."""

import pytest
from pydantic import ValidationError

from synthorg.budget.call_analytics_config import CallAnalyticsConfig, RetryAlertConfig
from synthorg.budget.coordination_config import OrchestrationAlertThresholds


@pytest.mark.unit
class TestRetryAlertConfig:
    """RetryAlertConfig validation."""

    def test_defaults(self) -> None:
        cfg = RetryAlertConfig()
        assert cfg.warn_rate == 0.10

    def test_custom_warn_rate(self) -> None:
        cfg = RetryAlertConfig(warn_rate=0.25)
        assert cfg.warn_rate == 0.25

    def test_zero_accepted(self) -> None:
        cfg = RetryAlertConfig(warn_rate=0.0)
        assert cfg.warn_rate == 0.0

    def test_one_accepted(self) -> None:
        cfg = RetryAlertConfig(warn_rate=1.0)
        assert cfg.warn_rate == 1.0

    def test_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RetryAlertConfig(warn_rate=1.1)

    def test_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RetryAlertConfig(warn_rate=-0.01)

    def test_frozen(self) -> None:
        cfg = RetryAlertConfig()
        with pytest.raises(ValidationError):
            cfg.warn_rate = 0.5  # type: ignore[misc]


@pytest.mark.unit
class TestCallAnalyticsConfig:
    """CallAnalyticsConfig validation and defaults."""

    def test_defaults(self) -> None:
        cfg = CallAnalyticsConfig()
        assert cfg.enabled is True
        assert isinstance(cfg.orchestration_alerts, OrchestrationAlertThresholds)
        assert isinstance(cfg.retry_alerts, RetryAlertConfig)

    def test_disabled(self) -> None:
        cfg = CallAnalyticsConfig(enabled=False)
        assert cfg.enabled is False

    def test_custom_retry_alerts(self) -> None:
        cfg = CallAnalyticsConfig(retry_alerts=RetryAlertConfig(warn_rate=0.20))
        assert cfg.retry_alerts.warn_rate == 0.20

    def test_custom_orchestration_alerts(self) -> None:
        cfg = CallAnalyticsConfig(
            orchestration_alerts=OrchestrationAlertThresholds(
                info=0.10, warn=0.40, critical=0.60
            )
        )
        assert cfg.orchestration_alerts.warn == 0.40

    def test_frozen(self) -> None:
        cfg = CallAnalyticsConfig()
        with pytest.raises(ValidationError):
            cfg.enabled = False  # type: ignore[misc]
