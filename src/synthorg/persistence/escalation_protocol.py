"""Escalation queue repository protocol."""

from typing import Protocol, runtime_checkable

from synthorg.communication.conflict_resolution.escalation.models import (
    Escalation,
    EscalationDecision,
    EscalationStatus,
)

_DEFAULT_LIMIT = 50
_DEFAULT_OFFSET = 0


@runtime_checkable
class EscalationQueueRepository(Protocol):
    """Persistence contract for the human escalation queue.

    Implementations persist escalations across process restarts.  All
    methods are async to accommodate DB-backed adapters without
    forcing the in-memory default to fake blocking I/O.
    """

    async def create(self, escalation: Escalation) -> None:
        """Persist a new PENDING escalation.

        Raises:
            ValueError: ``escalation.id`` already exists.
        """
        ...

    async def get(self, escalation_id: str) -> Escalation | None:
        """Return the escalation by ID, or ``None`` if missing."""
        ...

    async def list_items(
        self,
        *,
        status: EscalationStatus | None = EscalationStatus.PENDING,
        limit: int = _DEFAULT_LIMIT,
        offset: int = _DEFAULT_OFFSET,
    ) -> tuple[tuple[Escalation, ...], int]:
        """Page over escalations, oldest-first by ``created_at``."""
        ...

    async def apply_decision(
        self,
        escalation_id: str,
        *,
        decision: EscalationDecision,
        decided_by: str,
    ) -> Escalation:
        """Transition a PENDING escalation to DECIDED with ``decision``.

        Raises:
            KeyError: ``escalation_id`` does not exist.
            ValueError: escalation is not PENDING.
        """
        ...

    async def cancel(
        self,
        escalation_id: str,
        *,
        cancelled_by: str,
    ) -> Escalation:
        """Transition a PENDING escalation to CANCELLED."""
        ...

    async def mark_expired(self, now_iso: str) -> tuple[str, ...]:
        """Transition any PENDING row with ``expires_at <= now`` to EXPIRED."""
        ...

    async def close(self) -> None:
        """Release any background resources."""
        ...
