"""Tests for model candidate selectors."""

import pytest

from synthorg.providers.routing.models import ResolvedModel
from synthorg.providers.routing.selector import (
    CheapestSelector,
    ModelCandidateSelector,
    QuotaAwareSelector,
)

pytestmark = pytest.mark.unit

# ── Fixtures ─────────────────────────────────────────────────────


def _model(
    provider: str,
    model_id: str,
    cost_input: float = 0.003,
    cost_output: float = 0.015,
) -> ResolvedModel:
    return ResolvedModel(
        provider_name=provider,
        model_id=model_id,
        cost_per_1k_input=cost_input,
        cost_per_1k_output=cost_output,
    )


CHEAP_A = _model("provider-a", "test-model-a", 0.001, 0.005)
EXPENSIVE_B = _model("provider-b", "test-model-b", 0.010, 0.050)
MID_C = _model("provider-c", "test-model-c", 0.003, 0.015)


# ── QuotaAwareSelector ──────────────────────────────────────────


class TestQuotaAwareSelector:
    def test_satisfies_protocol(self) -> None:
        selector = QuotaAwareSelector()
        assert isinstance(selector, ModelCandidateSelector)

    def test_empty_quota_map_picks_cheapest(self) -> None:
        selector = QuotaAwareSelector()
        result = selector.select((EXPENSIVE_B, CHEAP_A, MID_C))
        assert result is CHEAP_A

    def test_prefers_provider_with_quota(self) -> None:
        selector = QuotaAwareSelector(
            provider_quota_available={"provider-a": False, "provider-b": True},
        )
        result = selector.select((CHEAP_A, EXPENSIVE_B))
        assert result is EXPENSIVE_B

    def test_cheapest_among_available(self) -> None:
        selector = QuotaAwareSelector(
            provider_quota_available={
                "provider-a": True,
                "provider-b": True,
                "provider-c": True,
            },
        )
        result = selector.select((EXPENSIVE_B, MID_C, CHEAP_A))
        assert result is CHEAP_A

    def test_all_exhausted_falls_back_to_cheapest(self) -> None:
        selector = QuotaAwareSelector(
            provider_quota_available={
                "provider-a": False,
                "provider-b": False,
            },
        )
        result = selector.select((EXPENSIVE_B, CHEAP_A))
        assert result is CHEAP_A

    def test_unknown_provider_assumed_available(self) -> None:
        selector = QuotaAwareSelector(
            provider_quota_available={"provider-a": False},
        )
        # provider-b not in map -> assumed available
        result = selector.select((CHEAP_A, EXPENSIVE_B))
        assert result is EXPENSIVE_B

    def test_single_candidate(self) -> None:
        selector = QuotaAwareSelector()
        result = selector.select((CHEAP_A,))
        assert result is CHEAP_A

    def test_single_candidate_exhausted(self) -> None:
        selector = QuotaAwareSelector(
            provider_quota_available={"provider-a": False},
        )
        result = selector.select((CHEAP_A,))
        assert result is CHEAP_A

    def test_cheapest_among_available_ignores_exhausted(self) -> None:
        selector = QuotaAwareSelector(
            provider_quota_available={
                "provider-a": False,
                "provider-b": True,
                "provider-c": True,
            },
        )
        result = selector.select((CHEAP_A, EXPENSIVE_B, MID_C))
        assert result is MID_C


# ── CheapestSelector ────────────────────────────────────────────


class TestCheapestSelector:
    def test_satisfies_protocol(self) -> None:
        selector = CheapestSelector()
        assert isinstance(selector, ModelCandidateSelector)

    def test_picks_cheapest(self) -> None:
        selector = CheapestSelector()
        result = selector.select((EXPENSIVE_B, MID_C, CHEAP_A))
        assert result is CHEAP_A

    def test_single_candidate(self) -> None:
        selector = CheapestSelector()
        result = selector.select((MID_C,))
        assert result is MID_C

    def test_equal_cost_deterministic(self) -> None:
        model_x = _model("provider-x", "test-x", 0.003, 0.015)
        model_y = _model("provider-y", "test-y", 0.003, 0.015)
        selector = CheapestSelector()
        # min() returns first equal element -- deterministic
        result = selector.select((model_x, model_y))
        assert result is model_x
        result = selector.select((model_y, model_x))
        assert result is model_y
