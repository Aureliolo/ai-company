"""Unit tests for the SelfImprovementService orchestrator."""

import pytest

from synthorg.meta.config import SelfImprovementConfig
from synthorg.meta.models import (
    OrgBudgetSummary,
    OrgCoordinationSummary,
    OrgErrorSummary,
    OrgEvolutionSummary,
    OrgPerformanceSummary,
    OrgScalingSummary,
    OrgSignalSnapshot,
    OrgTelemetrySummary,
    ProposalAltitude,
    ProposalStatus,
    RolloutOutcome,
)
from synthorg.meta.service import SelfImprovementService

pytestmark = pytest.mark.unit


def _snap(
    *,
    quality: float = 7.5,
    success: float = 0.85,
    days_left: int | None = None,
    coord_ratio: float = 0.3,
) -> OrgSignalSnapshot:
    return OrgSignalSnapshot(
        performance=OrgPerformanceSummary(
            avg_quality_score=quality,
            avg_success_rate=success,
            avg_collaboration_score=6.0,
            agent_count=10,
        ),
        budget=OrgBudgetSummary(
            total_spend_usd=150.0,
            productive_ratio=0.6,
            coordination_ratio=coord_ratio,
            system_ratio=0.1,
            days_until_exhausted=days_left,
            forecast_confidence=0.8,
            orchestration_overhead=0.5,
        ),
        coordination=OrgCoordinationSummary(),
        scaling=OrgScalingSummary(),
        errors=OrgErrorSummary(),
        evolution=OrgEvolutionSummary(),
        telemetry=OrgTelemetrySummary(),
    )


class TestSelfImprovementService:
    """SelfImprovementService tests."""

    def _svc(
        self,
        *,
        config_tuning: bool = True,
        architecture: bool = False,
        prompt_tuning: bool = False,
    ) -> SelfImprovementService:
        cfg = SelfImprovementConfig(
            enabled=True,
            config_tuning_enabled=config_tuning,
            architecture_proposals_enabled=architecture,
            prompt_tuning_enabled=prompt_tuning,
        )
        return SelfImprovementService(config=cfg)

    async def test_no_triggers_returns_empty(self) -> None:
        svc = self._svc()
        result = await svc.run_cycle(_snap())
        assert result == ()

    async def test_quality_declining_produces_proposal(self) -> None:
        svc = self._svc()
        result = await svc.run_cycle(_snap(quality=4.0))
        assert len(result) == 1
        assert all(p.altitude == ProposalAltitude.CONFIG_TUNING for p in result)

    async def test_budget_overrun_produces_proposal(self) -> None:
        svc = self._svc()
        result = await svc.run_cycle(_snap(days_left=7))
        assert len(result) == 1
        sources = {p.source_rule for p in result}
        assert "budget_overrun" in sources

    async def test_multiple_altitudes_enabled(self) -> None:
        svc = self._svc(
            config_tuning=True,
            prompt_tuning=True,
        )
        # Quality declining targets both config_tuning and prompt_tuning.
        result = await svc.run_cycle(_snap(quality=4.0))
        altitudes = {p.altitude for p in result}
        assert ProposalAltitude.CONFIG_TUNING in altitudes
        assert ProposalAltitude.PROMPT_TUNING in altitudes

    async def test_disabled_altitude_filtered(self) -> None:
        svc = self._svc(
            config_tuning=True,
            architecture=False,
        )
        # Coordination cost ratio targets both config_tuning and arch.
        result = await svc.run_cycle(_snap(coord_ratio=0.5))
        assert result, "expected at least one proposal for coord_ratio=0.5"
        altitudes = {p.altitude for p in result}
        assert ProposalAltitude.CONFIG_TUNING in altitudes
        assert ProposalAltitude.ARCHITECTURE not in altitudes

    async def test_rollout_execution(self) -> None:
        svc = self._svc()
        proposals = await svc.run_cycle(_snap(quality=4.0))
        assert len(proposals) >= 1
        approved = proposals[0].model_copy(
            update={
                "status": ProposalStatus.APPROVED,
                "decided_at": proposals[0].proposed_at,
                "decided_by": "test-approver",
                "decision_reason": "Unit test approval",
            },
        )
        rollout_result = await svc.execute_rollout(approved)
        assert rollout_result.outcome == RolloutOutcome.SUCCESS
