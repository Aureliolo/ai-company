"""Unit tests for confidence adjustment strategies."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.memory.backends.inmemory.adapter import InMemoryBackend
from synthorg.meta.chief_of_staff.learning import (
    BayesianConfidenceAdjuster,
    ExponentialMovingAverageAdjuster,
)
from synthorg.meta.chief_of_staff.models import ProposalOutcome
from synthorg.meta.chief_of_staff.outcome_store import MemoryBackendOutcomeStore
from synthorg.meta.models import (
    ConfigChange,
    ImprovementProposal,
    ProposalAltitude,
    ProposalRationale,
    RollbackOperation,
    RollbackPlan,
)

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 4, 15, 12, 0, 0, tzinfo=UTC)
_AGENT_ID = NotBlankStr("chief-of-staff")


def _make_proposal(
    *,
    confidence: float = 0.6,
    source_rule: str | None = "quality_declining",
) -> ImprovementProposal:
    return ImprovementProposal(
        altitude=ProposalAltitude.CONFIG_TUNING,
        title="Lower quality threshold",
        description="Reduce quality threshold by 5%",
        rationale=ProposalRationale(
            signal_summary="Quality declining",
            pattern_detected="Sustained quality drop",
            expected_impact="Better agent performance",
            confidence_reasoning="Historical data supports this",
        ),
        config_changes=(
            ConfigChange(
                path="quality.threshold",
                old_value=0.8,
                new_value=0.75,
                description="Lower quality threshold",
            ),
        ),
        rollback_plan=RollbackPlan(
            operations=(
                RollbackOperation(
                    operation_type="revert_config",
                    target="quality_threshold",
                    description="Restore quality threshold",
                ),
            ),
            validation_check="Verify quality metric",
        ),
        confidence=confidence,
        source_rule=source_rule,
    )


async def _store_with_outcomes(
    *,
    approved: int = 0,
    rejected: int = 0,
    rule: str = "quality_declining",
    min_outcomes: int = 1,
) -> MemoryBackendOutcomeStore:
    backend = InMemoryBackend()
    await backend.connect()
    store = MemoryBackendOutcomeStore(
        backend=backend,
        agent_id=_AGENT_ID,
        min_outcomes=min_outcomes,
    )
    for _ in range(approved):
        await store.record_outcome(
            ProposalOutcome(
                proposal_id=uuid4(),
                title="Test",
                altitude=ProposalAltitude.CONFIG_TUNING,
                source_rule=rule,
                decision="approved",
                confidence_at_decision=0.6,
                decided_at=_NOW,
                decided_by="reviewer",
            ),
        )
    for _ in range(rejected):
        await store.record_outcome(
            ProposalOutcome(
                proposal_id=uuid4(),
                title="Test",
                altitude=ProposalAltitude.CONFIG_TUNING,
                source_rule=rule,
                decision="rejected",
                confidence_at_decision=0.6,
                decided_at=_NOW,
                decided_by="reviewer",
            ),
        )
    return store


# ── EMA Adjuster ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "adjuster_factory",
    [
        pytest.param(ExponentialMovingAverageAdjuster, id="ema"),
        pytest.param(BayesianConfidenceAdjuster, id="bayesian"),
    ],
)
class TestAdjusterCommon:
    """Tests shared between both adjuster strategies."""

    async def test_no_source_rule_returns_unchanged(
        self,
        adjuster_factory: type,
    ) -> None:
        store = await _store_with_outcomes(approved=5)
        adjuster = adjuster_factory()
        proposal = _make_proposal(source_rule=None, confidence=0.6)
        result = await adjuster.adjust(proposal, store)
        assert result.confidence == pytest.approx(0.6)

    async def test_no_history_returns_unchanged(
        self,
        adjuster_factory: type,
    ) -> None:
        store = await _store_with_outcomes(min_outcomes=3)
        adjuster = adjuster_factory()
        proposal = _make_proposal(confidence=0.6)
        result = await adjuster.adjust(proposal, store)
        assert result.confidence == pytest.approx(0.6)

    async def test_returns_new_instance(
        self,
        adjuster_factory: type,
    ) -> None:
        store = await _store_with_outcomes(approved=5, rejected=5)
        adjuster = adjuster_factory()
        proposal = _make_proposal()
        result = await adjuster.adjust(proposal, store)
        assert result is not proposal


class TestEMAConfidenceAdjuster:
    """ExponentialMovingAverageAdjuster tests."""

    def test_name(self) -> None:
        adjuster = ExponentialMovingAverageAdjuster()
        assert adjuster.name == "ema"

    async def test_high_approval_boosts(self) -> None:
        store = await _store_with_outcomes(approved=8, rejected=2)
        adjuster = ExponentialMovingAverageAdjuster(alpha=0.5)
        proposal = _make_proposal(confidence=0.6)
        # adjusted = 0.5 * 0.6 + 0.5 * 0.8 = 0.7
        result = await adjuster.adjust(proposal, store)
        assert result.confidence == pytest.approx(0.7)

    async def test_low_approval_dampens(self) -> None:
        store = await _store_with_outcomes(approved=2, rejected=8)
        adjuster = ExponentialMovingAverageAdjuster(alpha=0.5)
        proposal = _make_proposal(confidence=0.6)
        # adjusted = 0.5 * 0.6 + 0.5 * 0.2 = 0.4
        result = await adjuster.adjust(proposal, store)
        assert result.confidence == pytest.approx(0.4)

    async def test_alpha_one_ignores_history(self) -> None:
        store = await _store_with_outcomes(approved=0, rejected=10)
        adjuster = ExponentialMovingAverageAdjuster(alpha=1.0)
        proposal = _make_proposal(confidence=0.6)
        result = await adjuster.adjust(proposal, store)
        assert result.confidence == pytest.approx(0.6)

    async def test_alpha_zero_uses_only_history(self) -> None:
        store = await _store_with_outcomes(approved=8, rejected=2)
        adjuster = ExponentialMovingAverageAdjuster(alpha=0.0)
        proposal = _make_proposal(confidence=0.6)
        result = await adjuster.adjust(proposal, store)
        assert result.confidence == pytest.approx(0.8)

    async def test_clamped_to_zero(self) -> None:
        store = await _store_with_outcomes(approved=0, rejected=10)
        adjuster = ExponentialMovingAverageAdjuster(alpha=0.0)
        proposal = _make_proposal(confidence=0.0)
        result = await adjuster.adjust(proposal, store)
        assert result.confidence == pytest.approx(0.0)

    async def test_clamped_to_one(self) -> None:
        store = await _store_with_outcomes(approved=10, rejected=0)
        adjuster = ExponentialMovingAverageAdjuster(alpha=0.0)
        proposal = _make_proposal(confidence=1.0)
        result = await adjuster.adjust(proposal, store)
        assert result.confidence == pytest.approx(1.0)


# ── Bayesian Adjuster ─────────────────────────────────────────────


class TestBayesianConfidenceAdjuster:
    """BayesianConfidenceAdjuster tests."""

    def test_name(self) -> None:
        adjuster = BayesianConfidenceAdjuster()
        assert adjuster.name == "bayesian"

    async def test_high_approval_boosts(self) -> None:
        store = await _store_with_outcomes(approved=8, rejected=2)
        adjuster = BayesianConfidenceAdjuster(
            prior_alpha=2.0,
            prior_beta=2.0,
            blend=0.7,
        )
        proposal = _make_proposal(confidence=0.6)
        # posterior = (2+8)/(2+2+10) = 10/14 ~ 0.714
        # adjusted = 0.7*0.6 + 0.3*0.714 ~ 0.42 + 0.214 ~ 0.634
        result = await adjuster.adjust(proposal, store)
        assert result.confidence > 0.6

    async def test_regularizes_small_samples(self) -> None:
        store = await _store_with_outcomes(
            approved=1,
            rejected=0,
            min_outcomes=1,
        )
        adjuster = BayesianConfidenceAdjuster(
            prior_alpha=2.0,
            prior_beta=2.0,
            blend=0.7,
        )
        proposal = _make_proposal(confidence=0.6)
        # posterior = (2+1)/(2+2+1) = 3/5 = 0.6
        # adjusted = 0.7*0.6 + 0.3*0.6 = 0.6 (prior regularizes)
        result = await adjuster.adjust(proposal, store)
        assert result.confidence == pytest.approx(0.6)

    async def test_clamped_within_bounds(self) -> None:
        store = await _store_with_outcomes(approved=10, rejected=0)
        adjuster = BayesianConfidenceAdjuster()
        proposal = _make_proposal(confidence=1.0)
        result = await adjuster.adjust(proposal, store)
        assert 0.0 <= result.confidence <= 1.0
