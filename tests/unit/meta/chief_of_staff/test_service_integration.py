"""Unit tests for SelfImprovementService CoS integration."""

from datetime import UTC, datetime

import pytest

from synthorg.memory.backends.inmemory.adapter import InMemoryBackend
from synthorg.meta.chief_of_staff.config import ChiefOfStaffConfig
from synthorg.meta.config import SelfImprovementConfig
from synthorg.meta.models import (
    ConfigChange,
    ImprovementProposal,
    ProposalAltitude,
    ProposalRationale,
    ProposalStatus,
    RollbackOperation,
    RollbackPlan,
)
from synthorg.meta.service import SelfImprovementService

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 4, 15, 12, 0, 0, tzinfo=UTC)


def _decided_proposal(
    *,
    status: ProposalStatus = ProposalStatus.APPROVED,
) -> ImprovementProposal:
    return ImprovementProposal(
        altitude=ProposalAltitude.CONFIG_TUNING,
        title="Test proposal",
        description="Test description",
        rationale=ProposalRationale(
            signal_summary="Quality declining",
            pattern_detected="Pattern",
            expected_impact="Impact",
            confidence_reasoning="Reasoning",
        ),
        config_changes=(
            ConfigChange(
                path="quality.threshold",
                old_value=0.8,
                new_value=0.75,
                description="Lower threshold",
            ),
        ),
        rollback_plan=RollbackPlan(
            operations=(
                RollbackOperation(
                    operation_type="revert_config",
                    target="quality.threshold",
                    description="Restore threshold",
                ),
            ),
            validation_check="Verify quality",
        ),
        confidence=0.7,
        source_rule="quality_declining",
        status=status,
        decided_at=_NOW,
        decided_by="reviewer",
        decision_reason="Looks good",
    )


class TestRecordDecision:
    """SelfImprovementService.record_decision tests."""

    async def test_records_approved_proposal(self) -> None:
        backend = InMemoryBackend()
        await backend.connect()
        cfg = SelfImprovementConfig(
            chief_of_staff=ChiefOfStaffConfig(learning_enabled=True),
        )
        svc = SelfImprovementService(
            config=cfg,
            memory_backend=backend,
        )
        proposal = _decided_proposal(status=ProposalStatus.APPROVED)
        await svc.record_decision(proposal)
        assert svc._outcome_store is not None
        outcomes = await svc._outcome_store.recent_outcomes()
        assert len(outcomes) == 1
        assert outcomes[0].decision == "approved"

    async def test_records_rejected_proposal(self) -> None:
        backend = InMemoryBackend()
        await backend.connect()
        cfg = SelfImprovementConfig(
            chief_of_staff=ChiefOfStaffConfig(learning_enabled=True),
        )
        svc = SelfImprovementService(
            config=cfg,
            memory_backend=backend,
        )
        proposal = _decided_proposal(status=ProposalStatus.REJECTED)
        await svc.record_decision(proposal)
        assert svc._outcome_store is not None
        outcomes = await svc._outcome_store.recent_outcomes()
        assert len(outcomes) == 1
        assert outcomes[0].decision == "rejected"

    async def test_skips_when_learning_disabled(self) -> None:
        cfg = SelfImprovementConfig(
            chief_of_staff=ChiefOfStaffConfig(learning_enabled=False),
        )
        svc = SelfImprovementService(config=cfg)
        proposal = _decided_proposal()
        await svc.record_decision(proposal)
        assert svc._outcome_store is None

    async def test_skips_missing_decided_at(self) -> None:
        backend = InMemoryBackend()
        await backend.connect()
        cfg = SelfImprovementConfig(
            chief_of_staff=ChiefOfStaffConfig(learning_enabled=True),
        )
        svc = SelfImprovementService(
            config=cfg,
            memory_backend=backend,
        )
        proposal = ImprovementProposal(
            altitude=ProposalAltitude.CONFIG_TUNING,
            title="Test",
            description="Test",
            rationale=ProposalRationale(
                signal_summary="s",
                pattern_detected="p",
                expected_impact="i",
                confidence_reasoning="c",
            ),
            config_changes=(
                ConfigChange(
                    path="x",
                    old_value=1,
                    new_value=2,
                    description="d",
                ),
            ),
            rollback_plan=RollbackPlan(
                operations=(
                    RollbackOperation(
                        operation_type="revert",
                        target="x",
                        description="r",
                    ),
                ),
                validation_check="v",
            ),
            confidence=0.5,
        )
        await svc.record_decision(proposal)
        assert svc._outcome_store is not None
        outcomes = await svc._outcome_store.recent_outcomes()
        assert len(outcomes) == 0

    async def test_skips_pending_status(self) -> None:
        backend = InMemoryBackend()
        await backend.connect()
        cfg = SelfImprovementConfig(
            chief_of_staff=ChiefOfStaffConfig(learning_enabled=True),
        )
        svc = SelfImprovementService(
            config=cfg,
            memory_backend=backend,
        )
        proposal = ImprovementProposal(
            altitude=ProposalAltitude.CONFIG_TUNING,
            title="Test",
            description="Test",
            rationale=ProposalRationale(
                signal_summary="s",
                pattern_detected="p",
                expected_impact="i",
                confidence_reasoning="c",
            ),
            config_changes=(
                ConfigChange(
                    path="x",
                    old_value=1,
                    new_value=2,
                    description="d",
                ),
            ),
            rollback_plan=RollbackPlan(
                operations=(
                    RollbackOperation(
                        operation_type="revert",
                        target="x",
                        description="r",
                    ),
                ),
                validation_check="v",
            ),
            confidence=0.5,
            status=ProposalStatus.PENDING,
        )
        await svc.record_decision(proposal)
        assert svc._outcome_store is not None
        outcomes = await svc._outcome_store.recent_outcomes()
        assert len(outcomes) == 0
