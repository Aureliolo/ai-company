"""Tests for ToolDisclosureMetrics."""

import pytest
from pydantic import ValidationError

from synthorg.tools.disclosure_metrics import ToolDisclosureMetrics


@pytest.mark.unit
class TestToolDisclosureMetrics:
    """Tests for ToolDisclosureMetrics model."""

    def test_defaults(self) -> None:
        metrics = ToolDisclosureMetrics()
        assert metrics.l1_tokens_injected == 0
        assert metrics.l2_tokens_loaded == 0
        assert metrics.l3_tokens_fetched == 0
        assert metrics.estimated_eager_tokens == 0
        assert metrics.token_savings == 0

    def test_token_savings_computed(self) -> None:
        metrics = ToolDisclosureMetrics(
            l1_tokens_injected=500,
            l2_tokens_loaded=2000,
            l3_tokens_fetched=300,
            estimated_eager_tokens=10000,
        )
        assert metrics.token_savings == 10000 - (500 + 2000 + 300)

    def test_token_savings_never_negative(self) -> None:
        metrics = ToolDisclosureMetrics(
            l1_tokens_injected=5000,
            l2_tokens_loaded=5000,
            l3_tokens_fetched=5000,
            estimated_eager_tokens=1000,
        )
        assert metrics.token_savings == 0

    def test_frozen(self) -> None:
        metrics = ToolDisclosureMetrics()
        with pytest.raises(ValidationError):
            metrics.l1_tokens_injected = 99  # type: ignore[misc]

    def test_negative_tokens_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ToolDisclosureMetrics(l1_tokens_injected=-1)

    def test_zero_eager_zero_savings(self) -> None:
        metrics = ToolDisclosureMetrics(
            l1_tokens_injected=100,
            estimated_eager_tokens=0,
        )
        assert metrics.token_savings == 0
