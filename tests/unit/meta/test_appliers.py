"""Unit tests for meta-loop proposal appliers."""

import pytest

from synthorg.meta.appliers.architecture_applier import (
    ArchitectureApplier,
)
from synthorg.meta.appliers.config_applier import ConfigApplier
from synthorg.meta.appliers.prompt_applier import PromptApplier
from synthorg.meta.models import (
    ArchitectureChange,
    ConfigChange,
    ImprovementProposal,
    PromptChange,
    ProposalAltitude,
    ProposalRationale,
    RollbackOperation,
    RollbackPlan,
)

pytestmark = pytest.mark.unit


def _rationale() -> ProposalRationale:
    return ProposalRationale(
        signal_summary="test",
        pattern_detected="test",
        expected_impact="test",
        confidence_reasoning="test",
    )


def _rollback() -> RollbackPlan:
    return RollbackPlan(
        operations=(
            RollbackOperation(
                operation_type="revert",
                target="x",
                description="revert x",
            ),
        ),
        validation_check="check x",
    )


class TestConfigApplier:
    """Config applier tests."""

    def test_altitude(self) -> None:
        applier = ConfigApplier()
        assert applier.altitude == ProposalAltitude.CONFIG_TUNING

    async def test_apply_success(self) -> None:
        applier = ConfigApplier()
        proposal = ImprovementProposal(
            altitude=ProposalAltitude.CONFIG_TUNING,
            title="test",
            description="test",
            rationale=_rationale(),
            config_changes=(
                ConfigChange(
                    path="a.b",
                    old_value=1,
                    new_value=2,
                    description="d",
                ),
                ConfigChange(
                    path="c.d",
                    old_value=3,
                    new_value=4,
                    description="d",
                ),
            ),
            rollback_plan=_rollback(),
            confidence=0.8,
        )
        result = await applier.apply(proposal)
        assert result.success
        assert result.changes_applied == 2

    async def test_dry_run(self) -> None:
        applier = ConfigApplier()
        proposal = ImprovementProposal(
            altitude=ProposalAltitude.CONFIG_TUNING,
            title="test",
            description="test",
            rationale=_rationale(),
            config_changes=(
                ConfigChange(
                    path="a.b",
                    old_value=1,
                    new_value=2,
                    description="d",
                ),
            ),
            rollback_plan=_rollback(),
            confidence=0.8,
        )
        result = await applier.dry_run(proposal)
        assert not result.success
        assert result.changes_applied == 0
        assert result.error_message == "dry_run not yet implemented"


class TestArchitectureApplier:
    """Architecture applier tests."""

    def test_altitude(self) -> None:
        applier = ArchitectureApplier()
        assert applier.altitude == ProposalAltitude.ARCHITECTURE

    async def test_apply_success(self) -> None:
        applier = ArchitectureApplier()
        proposal = ImprovementProposal(
            altitude=ProposalAltitude.ARCHITECTURE,
            title="test",
            description="test",
            rationale=_rationale(),
            architecture_changes=(
                ArchitectureChange(
                    operation="create_role",
                    target_name="x",
                    description="d",
                ),
            ),
            rollback_plan=_rollback(),
            confidence=0.8,
        )
        result = await applier.apply(proposal)
        assert result.success
        assert result.changes_applied == 1


class TestPromptApplier:
    """Prompt applier tests."""

    def test_altitude(self) -> None:
        applier = PromptApplier()
        assert applier.altitude == ProposalAltitude.PROMPT_TUNING

    async def test_apply_success(self) -> None:
        applier = PromptApplier()
        proposal = ImprovementProposal(
            altitude=ProposalAltitude.PROMPT_TUNING,
            title="test",
            description="test",
            rationale=_rationale(),
            prompt_changes=(
                PromptChange(
                    principle_text="test",
                    target_scope="all",
                    description="d",
                ),
            ),
            rollback_plan=_rollback(),
            confidence=0.8,
        )
        result = await applier.apply(proposal)
        assert result.success
        assert result.changes_applied == 1

    async def test_dry_run(self) -> None:
        applier = PromptApplier()
        proposal = ImprovementProposal(
            altitude=ProposalAltitude.PROMPT_TUNING,
            title="test",
            description="test",
            rationale=_rationale(),
            prompt_changes=(
                PromptChange(
                    principle_text="test",
                    target_scope="all",
                    description="d",
                ),
            ),
            rollback_plan=_rollback(),
            confidence=0.8,
        )
        result = await applier.dry_run(proposal)
        assert not result.success
        assert result.error_message == "dry_run not yet implemented"
