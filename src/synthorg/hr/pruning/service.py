"""Pruning service -- performance-driven agent removal with human approval.

Periodically evaluates active agents against pruning policies, creates
approval items for eligible candidates, and delegates to OffboardingService
once human approval is granted.
"""

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

from synthorg.core.approval import ApprovalItem
from synthorg.core.enums import ApprovalRiskLevel, ApprovalStatus
from synthorg.core.types import NotBlankStr
from synthorg.hr.enums import FiringReason
from synthorg.hr.models import FiringRequest
from synthorg.hr.pruning.models import (
    PruningEvaluation,
    PruningJobRun,
    PruningRecord,
    PruningRequest,
    PruningServiceConfig,
)
from synthorg.observability import get_logger
from synthorg.observability.events.hr import (
    HR_PRUNING_AGENT_ELIGIBLE,
    HR_PRUNING_APPROVAL_DEDUP_SKIP,
    HR_PRUNING_APPROVAL_SUBMITTED,
    HR_PRUNING_APPROVED,
    HR_PRUNING_CYCLE_COMPLETE,
    HR_PRUNING_CYCLE_STARTED,
    HR_PRUNING_OFFBOARDED,
    HR_PRUNING_POLICY_ERROR,
    HR_PRUNING_REJECTED,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from synthorg.api.approval_store import ApprovalStore
    from synthorg.core.agent import AgentIdentity
    from synthorg.hr.offboarding_service import OffboardingService
    from synthorg.hr.performance.tracker import PerformanceTracker
    from synthorg.hr.pruning.policy import PruningPolicy
    from synthorg.hr.registry import AgentRegistryService

logger = get_logger(__name__)

_ACTION_TYPE = "hr:prune"


class PruningService:
    """Orchestrates performance-driven agent pruning with human approval.

    Args:
        policies: Pruning policy strategies to evaluate.
        registry: Agent registry for listing active agents.
        tracker: Performance tracker for snapshots.
        approval_store: Approval store for human decisions.
        offboarding_service: Service to delegate offboarding to.
        config: Pruning service configuration.
        on_notification: Optional callback for completion notifications.
    """

    def __init__(  # noqa: PLR0913
        self,
        *,
        policies: tuple[PruningPolicy, ...],
        registry: AgentRegistryService,
        tracker: PerformanceTracker,
        approval_store: ApprovalStore,
        offboarding_service: OffboardingService,
        config: PruningServiceConfig | None = None,
        on_notification: (Callable[[PruningRecord], Awaitable[None]] | None) = None,
    ) -> None:
        self._policies = policies
        self._registry = registry
        self._tracker = tracker
        self._approval_store = approval_store
        self._offboarding_service = offboarding_service
        self._config = config or PruningServiceConfig()
        self._on_notification = on_notification
        self._task: asyncio.Task[None] | None = None
        self._wake_event = asyncio.Event()
        self._pending_requests: dict[str, PruningRequest] = {}
        self._completed: list[PruningRecord] = []

    @property
    def is_running(self) -> bool:
        """Whether the scheduler loop is currently active."""
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        """Start the background pruning scheduler."""
        if self.is_running:
            return
        self._wake_event.clear()
        self._task = asyncio.create_task(
            self._run_loop(),
            name="pruning-scheduler",
        )

    async def stop(self) -> None:
        """Stop the background scheduler gracefully."""
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    def wake(self) -> None:
        """Trigger an early pruning cycle."""
        self._wake_event.set()

    async def run_pruning_cycle(
        self,
        *,
        now: datetime | None = None,
    ) -> PruningJobRun:
        """Execute a single pruning evaluation cycle.

        Args:
            now: Override for current time (testing).

        Returns:
            Job run metadata.
        """
        if now is None:
            now = datetime.now(UTC)

        cycle_start = datetime.now(UTC)
        job_id = NotBlankStr(str(uuid4()))
        logger.info(HR_PRUNING_CYCLE_STARTED, job_id=str(job_id))

        active_agents = await self._registry.list_active()
        errors: list[NotBlankStr] = []

        eligible = await self._evaluate_all(active_agents, errors)
        approvals = await self._submit_approvals(eligible, errors)
        await self._process_decided_approvals()

        elapsed = (datetime.now(UTC) - cycle_start).total_seconds()
        job_run = PruningJobRun(
            job_id=job_id,
            run_at=now,
            agents_evaluated=len(active_agents),
            agents_eligible=len(eligible),
            approval_requests_created=approvals,
            elapsed_seconds=elapsed,
            errors=tuple(errors),
        )

        logger.info(
            HR_PRUNING_CYCLE_COMPLETE,
            job_id=str(job_id),
            agents_evaluated=len(active_agents),
            agents_eligible=len(eligible),
            approvals_created=approvals,
            elapsed_seconds=elapsed,
        )
        return job_run

    async def _evaluate_all(
        self,
        agents: tuple[AgentIdentity, ...],
        errors: list[NotBlankStr],
    ) -> list[tuple[AgentIdentity, PruningEvaluation]]:
        """Evaluate all agents against policies, collecting errors."""
        eligible: list[tuple[AgentIdentity, PruningEvaluation]] = []
        for agent in agents:
            try:
                evaluation = await self._evaluate_agent(
                    NotBlankStr(str(agent.id)),
                )
                if evaluation.eligible:
                    eligible.append((agent, evaluation))
                    logger.info(
                        HR_PRUNING_AGENT_ELIGIBLE,
                        agent_id=str(agent.id),
                        policy=str(evaluation.policy_name),
                    )
            except MemoryError, RecursionError:
                raise
            except Exception as exc:
                errors.append(NotBlankStr(f"{agent.id}: {exc}"))
                logger.warning(
                    HR_PRUNING_POLICY_ERROR,
                    agent_id=str(agent.id),
                    error=str(exc),
                )
        return eligible

    async def _submit_approvals(
        self,
        eligible: list[tuple[AgentIdentity, PruningEvaluation]],
        errors: list[NotBlankStr],
    ) -> int:
        """Submit approval requests for eligible agents."""
        created = 0
        for agent, evaluation in eligible:
            if created >= self._config.max_approvals_per_cycle:
                break
            try:
                if await self._submit_approval(agent, evaluation):
                    created += 1
            except MemoryError, RecursionError:
                raise
            except Exception as exc:
                errors.append(NotBlankStr(f"approval {agent.id}: {exc}"))
                logger.warning(
                    HR_PRUNING_POLICY_ERROR,
                    agent_id=str(agent.id),
                    error=str(exc),
                )
        return created

    async def _evaluate_agent(
        self,
        agent_id: NotBlankStr,
    ) -> PruningEvaluation:
        """Evaluate a single agent against all policies.

        Returns the first eligible evaluation, or the last ineligible one.
        """
        snapshot = await self._tracker.get_snapshot(agent_id)

        last_evaluation = None
        for policy in self._policies:
            evaluation = await policy.evaluate(agent_id, snapshot)
            if evaluation.eligible:
                return evaluation
            last_evaluation = evaluation

        if last_evaluation is not None:
            return last_evaluation

        return PruningEvaluation(
            agent_id=agent_id,
            eligible=False,
            reasons=(),
            scores={},
            policy_name=NotBlankStr("none"),
            snapshot=snapshot,
            evaluated_at=datetime.now(UTC),
        )

    async def _submit_approval(
        self,
        agent: AgentIdentity,
        evaluation: PruningEvaluation,
    ) -> bool:
        """Create an approval item for a pruning candidate.

        Returns True if a new approval was created, False if deduped.
        """
        agent_id = str(agent.id)

        pending = await self._approval_store.list_items(
            action_type=_ACTION_TYPE,
            status=ApprovalStatus.PENDING,
        )
        for item in pending:
            if item.metadata.get("agent_id") == agent_id:
                logger.debug(
                    HR_PRUNING_APPROVAL_DEDUP_SKIP,
                    agent_id=agent_id,
                )
                return False

        approval_id = NotBlankStr(str(uuid4()))
        expires_at = datetime.now(UTC) + timedelta(
            days=self._config.approval_expiry_days,
        )

        reason_summary = ", ".join(str(r) for r in evaluation.reasons)

        approval = ApprovalItem(
            id=approval_id,
            action_type=NotBlankStr(_ACTION_TYPE),
            title=NotBlankStr(f"Prune agent {agent.name}"),
            description=NotBlankStr(
                f"Policy {evaluation.policy_name}: {reason_summary}"
                if reason_summary
                else f"Policy {evaluation.policy_name}: eligible for pruning"
            ),
            requested_by=NotBlankStr("system"),
            risk_level=ApprovalRiskLevel.CRITICAL,
            status=ApprovalStatus.PENDING,
            created_at=datetime.now(UTC),
            expires_at=expires_at,
            metadata={
                "agent_id": agent_id,
                "policy_name": str(evaluation.policy_name),
                "reason_summary": reason_summary,
            },
        )
        await self._approval_store.add(approval)

        request = PruningRequest(
            agent_id=NotBlankStr(agent_id),
            agent_name=agent.name,
            evaluation=evaluation,
            approval_id=approval_id,
            status=ApprovalStatus.PENDING,
            created_at=datetime.now(UTC),
        )
        self._pending_requests[agent_id] = request

        logger.info(
            HR_PRUNING_APPROVAL_SUBMITTED,
            agent_id=agent_id,
            approval_id=str(approval_id),
            policy=str(evaluation.policy_name),
        )
        return True

    async def _process_decided_approvals(self) -> None:
        """Poll for decided approvals and process them."""
        approved_items = await self._approval_store.list_items(
            action_type=_ACTION_TYPE,
            status=ApprovalStatus.APPROVED,
        )
        for item in approved_items:
            await self._handle_approved(item)

        rejected_items = await self._approval_store.list_items(
            action_type=_ACTION_TYPE,
            status=ApprovalStatus.REJECTED,
        )
        for item in rejected_items:
            self._handle_rejected(item)

    async def _handle_approved(self, item: ApprovalItem) -> None:
        """Execute offboarding after approval."""
        agent_id = item.metadata.get("agent_id")
        if not agent_id:
            logger.warning(
                HR_PRUNING_APPROVED,
                approval_id=str(item.id),
                error="Missing agent_id in approval metadata",
            )
            return

        agent = await self._registry.get(NotBlankStr(agent_id))
        if agent is None:
            logger.warning(
                HR_PRUNING_APPROVED,
                agent_id=agent_id,
                error="Agent not found in registry",
            )
            self._pending_requests.pop(agent_id, None)
            return

        logger.info(
            HR_PRUNING_APPROVED,
            agent_id=agent_id,
            approval_id=str(item.id),
        )

        firing_request = FiringRequest(
            agent_id=NotBlankStr(agent_id),
            agent_name=agent.name,
            reason=FiringReason.PERFORMANCE,
            requested_by=NotBlankStr("pruning_service"),
            details=(
                f"Pruning approval {item.id}: "
                f"{item.metadata.get('reason_summary', 'performance-based')}"
            ),
            created_at=datetime.now(UTC),
        )

        try:
            offboarding_result = await self._offboarding_service.offboard(
                firing_request,
            )
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.exception(
                HR_PRUNING_POLICY_ERROR,
                agent_id=agent_id,
                error="Offboarding failed after approval",
            )
            return

        pending_request = self._pending_requests.pop(agent_id, None)

        record = PruningRecord(
            agent_id=NotBlankStr(agent_id),
            agent_name=agent.name,
            pruning_request_id=(
                pending_request.id if pending_request else NotBlankStr("unknown")
            ),
            offboarding_record_id=offboarding_result.firing_request_id,
            reason=NotBlankStr(
                item.metadata.get("reason_summary", "performance-based"),
            ),
            approval_id=item.id,
            initiated_by=NotBlankStr("system"),
            created_at=firing_request.created_at,
            completed_at=datetime.now(UTC),
        )
        self._completed.append(record)

        logger.info(
            HR_PRUNING_OFFBOARDED,
            agent_id=agent_id,
            approval_id=str(item.id),
        )

        if self._on_notification is not None:
            try:
                await self._on_notification(record)
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.warning(
                    HR_PRUNING_OFFBOARDED,
                    agent_id=agent_id,
                    note="notification callback failed",
                )

    def _handle_rejected(self, item: ApprovalItem) -> None:
        """Clean up after a rejected approval."""
        agent_id = item.metadata.get("agent_id", "unknown")
        self._pending_requests.pop(agent_id, None)
        logger.info(
            HR_PRUNING_REJECTED,
            agent_id=agent_id,
            approval_id=str(item.id),
            reason=str(item.decision_reason) if item.decision_reason else None,
        )

    async def _run_loop(self) -> None:
        """Sleep-and-check scheduler loop."""
        while True:
            self._wake_event.clear()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(
                    self._wake_event.wait(),
                    timeout=self._config.evaluation_interval_seconds,
                )
            try:
                await self.run_pruning_cycle()
            except MemoryError, RecursionError:
                raise
            except Exception:
                logger.exception(
                    HR_PRUNING_CYCLE_COMPLETE,
                    error="Unexpected error in pruning scheduler loop",
                )
