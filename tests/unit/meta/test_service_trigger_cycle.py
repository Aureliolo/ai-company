"""Tests for SelfImprovementService.trigger_cycle()."""

from unittest.mock import AsyncMock

import pytest
import structlog.testing

from synthorg.approval.protocol import ApprovalStoreProtocol
from synthorg.meta.config import SelfImprovementConfig
from synthorg.meta.errors import SelfImprovementTriggerError
from synthorg.meta.models import (
    ImprovementCycleResult,
    OrgBudgetSummary,
    OrgCoordinationSummary,
    OrgErrorSummary,
    OrgEvolutionSummary,
    OrgPerformanceSummary,
    OrgScalingSummary,
    OrgSignalSnapshot,
    OrgTelemetrySummary,
)
from synthorg.meta.service import SelfImprovementService
from synthorg.observability.events.meta import META_CYCLE_TRIGGERED


def _snapshot() -> OrgSignalSnapshot:
    return OrgSignalSnapshot(
        performance=OrgPerformanceSummary(
            avg_quality_score=7.5,
            avg_success_rate=0.85,
            avg_collaboration_score=6.0,
            agent_count=10,
        ),
        budget=OrgBudgetSummary(
            total_spend=10.0,
            productive_ratio=0.6,
            coordination_ratio=0.3,
            system_ratio=0.1,
            days_until_exhausted=None,
            forecast_confidence=0.5,
            orchestration_overhead=0.5,
        ),
        coordination=OrgCoordinationSummary(),
        scaling=OrgScalingSummary(),
        errors=OrgErrorSummary(),
        evolution=OrgEvolutionSummary(),
        telemetry=OrgTelemetrySummary(),
    )


async def _builder() -> OrgSignalSnapshot:
    return _snapshot()


def _service(
    *,
    snapshot_builder: object | None = _builder,
) -> SelfImprovementService:
    cfg = SelfImprovementConfig(
        enabled=False,  # bypass approval-store guard
    )
    return SelfImprovementService(
        config=cfg,
        approval_store=AsyncMock(spec=ApprovalStoreProtocol),
        snapshot_builder=snapshot_builder,  # type: ignore[arg-type]
    )


class TestTriggerCycle:
    @pytest.mark.unit
    async def test_returns_cycle_result(self) -> None:
        service = _service()
        result = await service.trigger_cycle()
        assert isinstance(result, ImprovementCycleResult)
        assert result.proposals_count == len(result.proposals)
        assert result.completed_at >= result.started_at

    @pytest.mark.unit
    async def test_emits_triggered_event(self) -> None:
        service = _service()
        with structlog.testing.capture_logs() as logs:
            await service.trigger_cycle()
        events = [e for e in logs if e.get("event") == META_CYCLE_TRIGGERED]
        assert events, "expected META_CYCLE_TRIGGERED log entry"
        assert "cycle_id" in events[0]
        assert "proposals_count" in events[0]

    @pytest.mark.unit
    async def test_no_builder_raises(self) -> None:
        service = _service(snapshot_builder=None)
        with pytest.raises(SelfImprovementTriggerError):
            await service.trigger_cycle()
