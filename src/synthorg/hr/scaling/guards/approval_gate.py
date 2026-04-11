"""Approval gate guard.

Routes scaling decisions through the existing ApprovalStore
for human approval. Creates ApprovalItem entries and returns
the original decisions unchanged; execution checks approval
status later.
"""

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

from synthorg.core.approval import ApprovalItem
from synthorg.core.enums import ApprovalRiskLevel, ApprovalStatus
from synthorg.core.types import NotBlankStr
from synthorg.hr.scaling.enums import ScalingActionType
from synthorg.observability import get_logger
from synthorg.observability.events.hr import HR_SCALING_GUARD_APPLIED

if TYPE_CHECKING:
    from synthorg.api.approval_store import ApprovalStore
    from synthorg.hr.scaling.models import ScalingDecision

logger = get_logger(__name__)

# Map scaling actions to approval risk levels.
_RISK_MAP: dict[str, ApprovalRiskLevel] = {
    ScalingActionType.HIRE: ApprovalRiskLevel.MEDIUM,
    ScalingActionType.PRUNE: ApprovalRiskLevel.CRITICAL,
}


class ApprovalGateGuard:
    """Routes decisions through the approval system.

    Creates ``ApprovalItem`` entries in the ``ApprovalStore`` for
    each decision and returns the original decisions unchanged
    (execution will check approval status later).

    Args:
        approval_store: Existing approval store to use.
        expiry_days: Days until approval items expire.
    """

    def __init__(
        self,
        *,
        approval_store: ApprovalStore,
        expiry_days: int = 7,
    ) -> None:
        self._store = approval_store
        self._expiry_days = expiry_days

    @property
    def name(self) -> NotBlankStr:
        """Guard identifier."""
        return NotBlankStr("approval_gate")

    async def filter(
        self,
        decisions: tuple[ScalingDecision, ...],
    ) -> tuple[ScalingDecision, ...]:
        """Create approval items for all actionable decisions.

        This is a side-effect-only guard: it creates ``ApprovalItem``
        entries in the ``ApprovalStore`` and returns the decisions
        unchanged so downstream code can execute approved actions
        (or defer execution pending human approval). NO_OP and HOLD
        decisions are skipped since they do not require approval.

        Approval-store write failures for a single decision are
        logged but do not abort the whole chain -- the decision is
        dropped (it has no corresponding approval entry and cannot
        be executed safely).

        Args:
            decisions: Incoming decisions.

        Returns:
            Decisions that either do not need approval or had an
            approval item successfully created.
        """
        surviving: list[ScalingDecision] = []
        for decision in decisions:
            if decision.action_type in {
                ScalingActionType.NO_OP,
                ScalingActionType.HOLD,
            }:
                surviving.append(decision)
                continue

            risk = _RISK_MAP.get(
                str(decision.action_type),
                ApprovalRiskLevel.MEDIUM,
            )

            title = (
                f"Scaling: {decision.action_type.value} "
                f"({decision.source_strategy.value})"
            )

            now = datetime.now(UTC)
            item = ApprovalItem(
                id=str(uuid4()),
                action_type=f"scaling:{decision.action_type.value}",
                title=title,
                description=str(decision.rationale),
                requested_by="scaling_service",
                risk_level=risk,
                status=ApprovalStatus.PENDING,
                metadata={
                    "scaling_decision_id": str(decision.id),
                    "source_strategy": str(decision.source_strategy),
                    "confidence": str(decision.confidence),
                },
                created_at=now,
                expires_at=now + timedelta(days=self._expiry_days),
            )

            try:
                await self._store.add(item)
            except MemoryError, RecursionError:
                raise
            except Exception as exc:
                logger.error(
                    HR_SCALING_GUARD_APPLIED,
                    guard="approval_gate",
                    action="approval_creation_failed",
                    decision_id=str(decision.id),
                    error=f"{type(exc).__name__}: {exc}",
                    exc_info=True,
                )
                # Drop the decision: without an approval item it
                # cannot be safely executed through the existing flow.
                continue

            logger.info(
                HR_SCALING_GUARD_APPLIED,
                guard="approval_gate",
                action="approval_created",
                approval_id=item.id,
                decision_id=str(decision.id),
                risk_level=risk.value,
            )
            surviving.append(decision)

        return tuple(surviving)
