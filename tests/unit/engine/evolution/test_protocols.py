"""Tests for evolution protocol structural subtyping."""

import pytest

from synthorg.engine.evolution.models import (
    AdaptationAxis,
    AdaptationDecision,
    AdaptationProposal,
)
from synthorg.engine.evolution.protocols import (
    AdaptationAdapter,
    AdaptationGuard,
    AdaptationProposer,
    EvolutionTrigger,
)
from synthorg.hr.enums import TrendDirection
from synthorg.hr.performance.inflection_protocol import (
    InflectionSink,
    PerformanceInflection,
)

# ── Stub implementations for structural subtyping checks ─────────


class _StubTrigger:
    """Minimal trigger satisfying the protocol."""

    @property
    def name(self) -> str:
        return "stub_trigger"

    async def should_trigger(self, *, agent_id: str, context: object) -> bool:
        return True


class _StubProposer:
    """Minimal proposer satisfying the protocol."""

    @property
    def name(self) -> str:
        return "stub_proposer"

    async def propose(
        self, *, agent_id: str, context: object
    ) -> tuple[AdaptationProposal, ...]:
        return ()


class _StubGuard:
    """Minimal guard satisfying the protocol."""

    @property
    def name(self) -> str:
        return "stub_guard"

    async def evaluate(self, proposal: AdaptationProposal) -> AdaptationDecision:
        return AdaptationDecision(
            proposal_id=proposal.id,
            approved=True,
            guard_name="stub_guard",
            reason="auto-approved",
        )


class _StubAdapter:
    """Minimal adapter satisfying the protocol."""

    @property
    def name(self) -> str:
        return "stub_adapter"

    @property
    def axis(self) -> AdaptationAxis:
        return AdaptationAxis.PROMPT_TEMPLATE

    async def apply(self, proposal: AdaptationProposal, agent_id: str) -> None:
        pass


class _StubInflectionSink:
    """Minimal inflection sink satisfying the protocol."""

    async def emit(self, inflection: PerformanceInflection) -> None:
        pass


# ── Protocol structural subtyping tests ──────────────────────────


class TestEvolutionTriggerProtocol:
    """EvolutionTrigger is a runtime-checkable protocol."""

    @pytest.mark.unit
    def test_stub_satisfies_protocol(self) -> None:
        assert isinstance(_StubTrigger(), EvolutionTrigger)

    @pytest.mark.unit
    def test_non_matching_class_fails(self) -> None:
        class _NoMatch:
            pass

        assert not isinstance(_NoMatch(), EvolutionTrigger)


class TestAdaptationProposerProtocol:
    """AdaptationProposer is a runtime-checkable protocol."""

    @pytest.mark.unit
    def test_stub_satisfies_protocol(self) -> None:
        assert isinstance(_StubProposer(), AdaptationProposer)


class TestAdaptationGuardProtocol:
    """AdaptationGuard is a runtime-checkable protocol."""

    @pytest.mark.unit
    def test_stub_satisfies_protocol(self) -> None:
        assert isinstance(_StubGuard(), AdaptationGuard)


class TestAdaptationAdapterProtocol:
    """AdaptationAdapter is a runtime-checkable protocol."""

    @pytest.mark.unit
    def test_stub_satisfies_protocol(self) -> None:
        assert isinstance(_StubAdapter(), AdaptationAdapter)


class TestInflectionSinkProtocol:
    """InflectionSink is a runtime-checkable protocol."""

    @pytest.mark.unit
    def test_stub_satisfies_protocol(self) -> None:
        assert isinstance(_StubInflectionSink(), InflectionSink)


class TestPerformanceInflectionModel:
    """PerformanceInflection model validation."""

    @pytest.mark.unit
    def test_valid_inflection(self) -> None:
        inflection = PerformanceInflection(
            agent_id="agent-1",
            metric_name="quality_score",
            window_size="7d",
            old_direction=TrendDirection.STABLE,
            new_direction=TrendDirection.DECLINING,
            slope=-0.08,
        )
        assert inflection.old_direction == TrendDirection.STABLE
        assert inflection.new_direction == TrendDirection.DECLINING
        assert inflection.slope == -0.08
        assert inflection.detected_at.tzinfo is not None

    @pytest.mark.unit
    def test_frozen(self) -> None:
        inflection = PerformanceInflection(
            agent_id="agent-1",
            metric_name="quality_score",
            window_size="7d",
            old_direction=TrendDirection.STABLE,
            new_direction=TrendDirection.IMPROVING,
            slope=0.05,
        )
        with pytest.raises(ValueError, match="frozen"):
            inflection.slope = 0.1  # type: ignore[misc]

    @pytest.mark.unit
    def test_nan_slope_rejected(self) -> None:
        with pytest.raises(ValueError, match="finite"):
            PerformanceInflection(
                agent_id="agent-1",
                metric_name="quality_score",
                window_size="7d",
                old_direction=TrendDirection.STABLE,
                new_direction=TrendDirection.IMPROVING,
                slope=float("nan"),
            )
