"""Concurrency regression tests for PruningService.

``_process_decided_approvals`` previously had a check-then-act race on
``_processed_approval_ids``: two concurrent cycles could both pass the
containment check and both invoke ``OffboardingService.offboard`` for the
same approval id. The fix claims the id under a lock before running
offboarding, so concurrent cycles must execute offboard at most once per
approval.
"""

import asyncio
from datetime import UTC, datetime

import pytest

from synthorg.api.approval_store import ApprovalStore
from synthorg.core.enums import ApprovalStatus
from synthorg.core.types import NotBlankStr
from synthorg.hr.models import FiringRequest, OffboardingRecord
from synthorg.hr.performance.models import AgentPerformanceSnapshot
from synthorg.hr.pruning.service import PruningService
from synthorg.hr.registry import AgentRegistryService
from tests.unit.hr.conftest import make_agent_identity

from .conftest import make_approval_item, make_performance_snapshot


class _SlowOffboardingService:
    """Offboarding stub that counts calls per agent and yields control."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self._started = asyncio.Event()
        self._release = asyncio.Event()

    def release(self) -> None:
        self._release.set()

    async def wait_started(self) -> None:
        await self._started.wait()

    async def offboard(self, request: FiringRequest) -> OffboardingRecord:
        self.calls.append(str(request.agent_id))
        self._started.set()
        await self._release.wait()
        now = datetime.now(UTC)
        return OffboardingRecord(
            agent_id=request.agent_id,
            agent_name=request.agent_name,
            firing_request_id=request.id,
            tasks_reassigned=(),
            memory_archive_id=None,
            org_memories_promoted=0,
            team_notification_sent=True,
            started_at=now,
            completed_at=now,
        )


class _FakeTracker:
    async def get_snapshot(
        self,
        agent_id: NotBlankStr,
        *,
        now: datetime | None = None,
    ) -> AgentPerformanceSnapshot:
        del now
        return make_performance_snapshot(agent_id=str(agent_id))


@pytest.mark.unit
class TestProcessDecidedApprovalsConcurrency:
    """Two concurrent cycles must not double-offboard the same agent."""

    async def test_concurrent_process_decided_approvals_no_double_offboard(
        self,
    ) -> None:
        registry = AgentRegistryService()
        agent = make_agent_identity(name="target-agent")
        await registry.register(agent)

        approval_store = ApprovalStore()
        approval = make_approval_item(
            approval_id="approval-conc-001",
            status=ApprovalStatus.APPROVED,
            decided_at=datetime.now(UTC),
            decided_by="ceo",
            metadata={
                "agent_id": str(agent.id),
                "policy_name": "threshold",
                "reason_summary": "test",
                "pruning_request_id": "req-001",
            },
        )
        await approval_store.add(approval)

        offboarding = _SlowOffboardingService()
        service = PruningService(
            policies=(),
            registry=registry,
            tracker=_FakeTracker(),  # type: ignore[arg-type]
            approval_store=approval_store,
            offboarding_service=offboarding,  # type: ignore[arg-type]
        )

        # Fire two concurrent cycles. First one should start offboarding
        # while the second one observes the claim and skips.
        task_a = asyncio.create_task(service._process_decided_approvals())
        await offboarding.wait_started()
        task_b = asyncio.create_task(service._process_decided_approvals())
        # Let B run its claim-check before releasing A.
        for _ in range(5):
            await asyncio.sleep(0)
        offboarding.release()

        await asyncio.gather(task_a, task_b)

        assert offboarding.calls == [str(agent.id)], (
            f"offboard must run exactly once per approval; got {offboarding.calls}"
        )
