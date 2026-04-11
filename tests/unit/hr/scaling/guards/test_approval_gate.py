"""Tests for approval gate guard."""

import pytest

from synthorg.api.approval_store import ApprovalStore
from synthorg.hr.scaling.enums import ScalingActionType
from synthorg.hr.scaling.guards.approval_gate import ApprovalGateGuard

from .conftest import make_decision


@pytest.mark.unit
class TestApprovalGateGuard:
    """ApprovalGateGuard approval item creation."""

    async def test_creates_approval_for_hire(self) -> None:
        store = ApprovalStore()
        guard = ApprovalGateGuard(approval_store=store)
        decisions = (make_decision(action_type=ScalingActionType.HIRE),)
        result = await guard.filter(decisions)
        # All decisions pass through (approval checked later).
        assert len(result) == 1
        # Approval item was created.
        items = await store.list_items()
        assert len(items) == 1
        assert items[0].action_type == "scaling:hire"

    async def test_creates_approval_for_prune(self) -> None:
        store = ApprovalStore()
        guard = ApprovalGateGuard(approval_store=store)
        decisions = (
            make_decision(
                action_type=ScalingActionType.PRUNE,
                target_agent_id="agent-001",
                target_role=None,
            ),
        )
        result = await guard.filter(decisions)
        assert len(result) == 1
        items = await store.list_items()
        assert len(items) == 1
        assert items[0].action_type == "scaling:prune"

    async def test_skips_noop_and_hold(self) -> None:
        store = ApprovalStore()
        guard = ApprovalGateGuard(approval_store=store)
        decisions = (
            make_decision(
                action_type=ScalingActionType.NO_OP,
                target_role=None,
            ),
        )
        await guard.filter(decisions)
        items = await store.list_items()
        assert len(items) == 0

    async def test_approval_metadata_contains_decision_id(self) -> None:
        store = ApprovalStore()
        guard = ApprovalGateGuard(approval_store=store)
        decision = make_decision(action_type=ScalingActionType.HIRE)
        await guard.filter((decision,))
        items = await store.list_items()
        assert items[0].metadata["scaling_decision_id"] == str(decision.id)

    async def test_name_property(self) -> None:
        store = ApprovalStore()
        guard = ApprovalGateGuard(approval_store=store)
        assert guard.name == "approval_gate"
