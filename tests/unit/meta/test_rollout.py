"""Unit tests for meta-loop rollout and regression detection."""

import pytest

from synthorg.meta.models import (
    ApplyResult,
    ConfigChange,
    ImprovementProposal,
    OrgBudgetSummary,
    OrgCoordinationSummary,
    OrgErrorSummary,
    OrgEvolutionSummary,
    OrgPerformanceSummary,
    OrgScalingSummary,
    OrgSignalSnapshot,
    OrgTelemetrySummary,
    ProposalAltitude,
    ProposalRationale,
    RegressionResult,
    RegressionThresholds,
    RegressionVerdict,
    RollbackOperation,
    RollbackPlan,
    RolloutOutcome,
)
from synthorg.meta.rollout.before_after import BeforeAfterRollout
from synthorg.meta.rollout.canary import CanarySubsetRollout
from synthorg.meta.rollout.regression.composite import (
    TieredRegressionDetector,
)
from synthorg.meta.rollout.regression.statistical import (
    StatisticalDetector,
)
from synthorg.meta.rollout.regression.threshold import (
    ThresholdDetector,
)
from synthorg.meta.rollout.rollback import RollbackExecutor

pytestmark = pytest.mark.unit


# ── Helpers ────────────────────────────────────────────────────────


def _snap(
    quality: float = 7.5,
    success: float = 0.85,
    spend: float = 100.0,
) -> OrgSignalSnapshot:
    return OrgSignalSnapshot(
        performance=OrgPerformanceSummary(
            avg_quality_score=quality,
            avg_success_rate=success,
            avg_collaboration_score=6.0,
            agent_count=10,
        ),
        budget=OrgBudgetSummary(
            total_spend_usd=spend,
            productive_ratio=0.6,
            coordination_ratio=0.3,
            system_ratio=0.1,
            forecast_confidence=0.8,
            orchestration_overhead=0.5,
        ),
        coordination=OrgCoordinationSummary(),
        scaling=OrgScalingSummary(),
        errors=OrgErrorSummary(),
        evolution=OrgEvolutionSummary(),
        telemetry=OrgTelemetrySummary(),
    )


def _proposal() -> ImprovementProposal:
    return ImprovementProposal(
        altitude=ProposalAltitude.CONFIG_TUNING,
        title="test",
        description="test",
        rationale=ProposalRationale(
            signal_summary="test",
            pattern_detected="test",
            expected_impact="test",
            confidence_reasoning="test",
        ),
        config_changes=(
            ConfigChange(
                path="a.b",
                old_value=1,
                new_value=2,
                description="d",
            ),
        ),
        rollback_plan=RollbackPlan(
            operations=(
                RollbackOperation(
                    operation_type="revert",
                    target="a.b",
                    previous_value=1,
                    description="revert a.b",
                ),
            ),
            validation_check="a.b equals 1",
        ),
        confidence=0.8,
    )


def _thresholds() -> RegressionThresholds:
    return RegressionThresholds()


# ── ThresholdDetector ──────────────────────────────────────────────


class TestThresholdDetector:
    """Threshold detector tests."""

    async def test_no_regression(self) -> None:
        detector = ThresholdDetector()
        result = await detector.check(
            baseline=_snap(quality=7.5),
            current=_snap(quality=7.4),
            thresholds=_thresholds(),
        )
        assert result.verdict == RegressionVerdict.NO_REGRESSION

    async def test_quality_breach(self) -> None:
        detector = ThresholdDetector()
        result = await detector.check(
            baseline=_snap(quality=8.0),
            current=_snap(quality=6.0),
            thresholds=RegressionThresholds(quality_drop=0.10),
        )
        assert result.verdict == RegressionVerdict.THRESHOLD_BREACH
        assert result.breached_metric == "quality"
        assert result.baseline_value == 8.0
        assert result.current_value == 6.0

    async def test_success_rate_breach(self) -> None:
        detector = ThresholdDetector()
        result = await detector.check(
            baseline=_snap(success=0.9),
            current=_snap(success=0.7),
            thresholds=RegressionThresholds(success_rate_drop=0.10),
        )
        assert result.verdict == RegressionVerdict.THRESHOLD_BREACH
        assert result.breached_metric == "success_rate"

    async def test_cost_increase_breach(self) -> None:
        detector = ThresholdDetector()
        result = await detector.check(
            baseline=_snap(spend=100.0),
            current=_snap(spend=130.0),
            thresholds=RegressionThresholds(cost_increase=0.20),
        )
        assert result.verdict == RegressionVerdict.THRESHOLD_BREACH
        assert result.breached_metric == "cost"

    async def test_no_breach_within_tolerance(self) -> None:
        detector = ThresholdDetector()
        result = await detector.check(
            baseline=_snap(quality=8.0),
            current=_snap(quality=7.5),
            thresholds=RegressionThresholds(quality_drop=0.10),
        )
        assert result.verdict == RegressionVerdict.NO_REGRESSION

    async def test_zero_baseline_skipped(self) -> None:
        detector = ThresholdDetector()
        result = await detector.check(
            baseline=_snap(quality=0.0),
            current=_snap(quality=5.0),
            thresholds=_thresholds(),
        )
        assert result.verdict == RegressionVerdict.NO_REGRESSION


# ── StatisticalDetector ────────────────────────────────────────────


class TestStatisticalDetector:
    """Statistical detector tests."""

    async def test_no_regression(self) -> None:
        detector = StatisticalDetector()
        result = await detector.check(
            baseline=_snap(quality=7.5),
            current=_snap(quality=7.3),
            thresholds=_thresholds(),
        )
        assert result.verdict == RegressionVerdict.NO_REGRESSION

    async def test_significant_regression(self) -> None:
        detector = StatisticalDetector()
        result = await detector.check(
            baseline=_snap(quality=8.0),
            current=_snap(quality=5.0),
            thresholds=_thresholds(),
        )
        assert result.verdict == RegressionVerdict.STATISTICAL_REGRESSION
        assert result.p_value is not None


# ── TieredRegressionDetector ──────────────────────────────────────


class TestTieredRegressionDetector:
    """Tiered detector tests."""

    async def test_threshold_takes_precedence(self) -> None:
        detector = TieredRegressionDetector()
        result = await detector.check(
            baseline=_snap(quality=8.0),
            current=_snap(quality=5.0),
            thresholds=RegressionThresholds(quality_drop=0.10),
        )
        assert result.verdict == RegressionVerdict.THRESHOLD_BREACH

    async def test_statistical_fires_when_threshold_ok(self) -> None:
        detector = TieredRegressionDetector()
        result = await detector.check(
            baseline=_snap(quality=8.0),
            current=_snap(quality=6.5),
            thresholds=RegressionThresholds(quality_drop=0.50),
        )
        assert result.verdict == RegressionVerdict.STATISTICAL_REGRESSION

    async def test_no_regression(self) -> None:
        detector = TieredRegressionDetector()
        result = await detector.check(
            baseline=_snap(quality=7.5),
            current=_snap(quality=7.4),
            thresholds=_thresholds(),
        )
        assert result.verdict == RegressionVerdict.NO_REGRESSION


# ── RollbackExecutor ──────────────────────────────────────────────


class TestRollbackExecutor:
    """Rollback executor tests."""

    async def test_executes_plan(self) -> None:
        executor = RollbackExecutor()
        result = await executor.execute(_proposal())
        assert result.success
        assert result.changes_applied == 1


# ── BeforeAfterRollout ────────────────────────────────────────────


class _StubApplier:
    @property
    def altitude(self) -> ProposalAltitude:
        return ProposalAltitude.CONFIG_TUNING

    async def apply(self, proposal: ImprovementProposal) -> ApplyResult:
        return ApplyResult(
            success=True,
            changes_applied=len(proposal.config_changes),
        )

    async def dry_run(self, proposal: ImprovementProposal) -> ApplyResult:
        _ = proposal
        return ApplyResult(success=True, changes_applied=0)


class _FailApplier:
    @property
    def altitude(self) -> ProposalAltitude:
        return ProposalAltitude.CONFIG_TUNING

    async def apply(self, proposal: ImprovementProposal) -> ApplyResult:
        _ = proposal
        return ApplyResult(
            success=False,
            error_message="apply failed",
            changes_applied=0,
        )

    async def dry_run(self, proposal: ImprovementProposal) -> ApplyResult:
        _ = proposal
        return ApplyResult(success=True, changes_applied=0)


class _StubDetector:
    @property
    def name(self) -> str:
        return "stub"

    async def check(
        self,
        *,
        baseline: OrgSignalSnapshot,
        current: OrgSignalSnapshot,
        thresholds: RegressionThresholds,
    ) -> RegressionResult:
        _ = baseline, current, thresholds
        return RegressionResult(
            verdict=RegressionVerdict.NO_REGRESSION,
        )


class TestBeforeAfterRollout:
    """Before/after rollout tests."""

    async def test_successful_rollout(self) -> None:
        rollout = BeforeAfterRollout()
        result = await rollout.execute(
            proposal=_proposal(),
            applier=_StubApplier(),
            detector=_StubDetector(),
        )
        assert result.outcome == RolloutOutcome.SUCCESS

    async def test_failed_apply(self) -> None:
        rollout = BeforeAfterRollout()
        result = await rollout.execute(
            proposal=_proposal(),
            applier=_FailApplier(),
            detector=_StubDetector(),
        )
        assert result.outcome == RolloutOutcome.FAILED


# ── CanarySubsetRollout ───────────────────────────────────────────


class TestCanarySubsetRollout:
    """Canary rollout tests."""

    async def test_successful_canary(self) -> None:
        rollout = CanarySubsetRollout(canary_fraction=0.2)
        result = await rollout.execute(
            proposal=_proposal(),
            applier=_StubApplier(),
            detector=_StubDetector(),
        )
        assert result.outcome == RolloutOutcome.SUCCESS

    async def test_failed_canary_apply(self) -> None:
        rollout = CanarySubsetRollout()
        result = await rollout.execute(
            proposal=_proposal(),
            applier=_FailApplier(),
            detector=_StubDetector(),
        )
        assert result.outcome == RolloutOutcome.FAILED
