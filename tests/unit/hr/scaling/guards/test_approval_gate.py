"""Tests for approval gate guard."""

import pytest

from synthorg.api.approval_store import ApprovalStore
from synthorg.hr.scaling.enums import ScalingActionType
from synthorg.hr.scaling.guards.approval_gate import ApprovalGateGuard

from .conftest import make_decision


@pytest.mark.unit
class TestApprovalGateGuard:
    """ApprovalGateGuard approval item creation."""

    @pytest.mark.parametrize(
        ("action_type", "target_agent_id", "target_role", "expected"),
        [
            (ScalingActionType.HIRE, None, "backend_developer", "scaling:hire"),
            (ScalingActionType.PRUNE, "agent-001", None, "scaling:prune"),
        ],
        ids=["hire", "prune"],
    )
    async def test_creates_approval(
        self,
        action_type: ScalingActionType,
        target_agent_id: str | None,
        target_role: str | None,
        expected: str,
    ) -> None:
        store = ApprovalStore()
        guard = ApprovalGateGuard(approval_store=store)
        decision = make_decision(
            action_type=action_type,
            target_agent_id=target_agent_id,
            target_role=target_role,
        )
        result = await guard.filter((decision,))
        assert len(result) == 1
        items = await store.list_items()
        assert len(items) == 1
        assert items[0].action_type == expected

    async def test_skips_noop_and_hold(self) -> None:
        store = ApprovalStore()
        guard = ApprovalGateGuard(approval_store=store)
        decisions = (
            make_decision(
                action_type=ScalingActionType.NO_OP,
                target_role=None,
            ),
            make_decision(
                action_type=ScalingActionType.HOLD,
                target_role=None,
            ),
        )
        result = await guard.filter(decisions)
        items = await store.list_items()
        assert len(items) == 0
        assert len(result) == 2

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
