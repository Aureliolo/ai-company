"""Tests for the ApproveAllGuard fallback."""

import pytest

from synthorg.engine.evolution.guards.approve_all import ApproveAllGuard
from synthorg.engine.evolution.models import (
    AdaptationAxis,
    AdaptationProposal,
    AdaptationSource,
)


def _proposal() -> AdaptationProposal:
    return AdaptationProposal(
        agent_id="agent-001",
        axis=AdaptationAxis.IDENTITY,
        description="test",
        changes={"name": "Evolved"},
        confidence=0.9,
        source=AdaptationSource.SUCCESS,
    )


@pytest.mark.unit
class TestApproveAllGuard:
    async def test_name(self) -> None:
        assert ApproveAllGuard().name == "ApproveAllGuard"

    async def test_always_approves(self) -> None:
        guard = ApproveAllGuard()
        decision = await guard.evaluate(_proposal())
        assert decision.approved is True
        assert "No guards configured" in decision.reason
        assert decision.guard_name == "ApproveAllGuard"
