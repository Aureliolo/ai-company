"""In-memory escalation queue store (#1418).

Process-local backend for the :class:`EscalationQueueStore` Protocol.
Used for tests and ephemeral deployments; production deployments
should use ``sqlite`` or ``postgres`` via
:func:`build_escalation_queue_store`.
"""

import asyncio
from datetime import UTC, datetime

from synthorg.communication.conflict_resolution.escalation.models import (
    Escalation,
    EscalationDecision,
    EscalationStatus,
)
from synthorg.communication.conflict_resolution.escalation.protocol import (
    EscalationQueueStore,
)

_DEFAULT_LIMIT = 50
_DEFAULT_OFFSET = 0


class InMemoryEscalationStore(EscalationQueueStore):
    """Dict-backed escalation queue with asyncio-safe writes."""

    def __init__(self) -> None:
        """Initialise an empty store."""
        self._rows: dict[str, Escalation] = {}
        self._lock = asyncio.Lock()

    async def create(self, escalation: Escalation) -> None:
        """Insert a PENDING escalation."""
        if escalation.status != EscalationStatus.PENDING:
            msg = "create() requires status=PENDING"
            raise ValueError(msg)
        async with self._lock:
            if escalation.id in self._rows:
                msg = f"Escalation {escalation.id!r} already exists"
                raise ValueError(msg)
            self._rows[escalation.id] = escalation

    async def get(self, escalation_id: str) -> Escalation | None:
        """Fetch by ID or return ``None``."""
        async with self._lock:
            return self._rows.get(escalation_id)

    async def list_items(
        self,
        *,
        status: EscalationStatus | None = EscalationStatus.PENDING,
        limit: int = _DEFAULT_LIMIT,
        offset: int = _DEFAULT_OFFSET,
    ) -> tuple[tuple[Escalation, ...], int]:
        """Return a page of rows ordered by ``created_at`` ascending."""
        if limit <= 0:
            msg = "limit must be positive"
            raise ValueError(msg)
        if offset < 0:
            msg = "offset must be non-negative"
            raise ValueError(msg)
        async with self._lock:
            if status is None:
                matching = list(self._rows.values())
            else:
                matching = [r for r in self._rows.values() if r.status == status]
        matching.sort(key=lambda r: r.created_at)
        total = len(matching)
        page = tuple(matching[offset : offset + limit])
        return page, total

    async def apply_decision(
        self,
        escalation_id: str,
        *,
        decision: EscalationDecision,
        decided_by: str,
    ) -> Escalation:
        """Transition PENDING -> DECIDED with ``decision``."""
        async with self._lock:
            row = self._rows.get(escalation_id)
            if row is None:
                msg = f"Escalation {escalation_id!r} not found"
                raise KeyError(msg)
            if row.status != EscalationStatus.PENDING:
                msg = (
                    f"Escalation {escalation_id!r} is {row.status}, "
                    "cannot apply a decision"
                )
                raise ValueError(msg)
            updated = row.model_copy(
                update={
                    "status": EscalationStatus.DECIDED,
                    "decision": decision,
                    "decided_at": datetime.now(UTC),
                    "decided_by": decided_by,
                },
            )
            self._rows[escalation_id] = updated
            return updated

    async def cancel(self, escalation_id: str, *, cancelled_by: str) -> Escalation:
        """Transition PENDING -> CANCELLED."""
        async with self._lock:
            row = self._rows.get(escalation_id)
            if row is None:
                msg = f"Escalation {escalation_id!r} not found"
                raise KeyError(msg)
            if row.status != EscalationStatus.PENDING:
                msg = f"Escalation {escalation_id!r} is {row.status}, cannot cancel"
                raise ValueError(msg)
            updated = row.model_copy(
                update={
                    "status": EscalationStatus.CANCELLED,
                    "decided_at": datetime.now(UTC),
                    "decided_by": cancelled_by,
                },
            )
            self._rows[escalation_id] = updated
            return updated

    async def mark_expired(self, now_iso: str) -> tuple[str, ...]:
        """Expire PENDING rows past their deadline."""
        now_dt = datetime.fromisoformat(now_iso)
        expired_ids: list[str] = []
        async with self._lock:
            for key, row in list(self._rows.items()):
                if (
                    row.status == EscalationStatus.PENDING
                    and row.expires_at is not None
                    and row.expires_at <= now_dt
                ):
                    self._rows[key] = row.model_copy(
                        update={
                            "status": EscalationStatus.EXPIRED,
                            "decided_at": now_dt,
                        },
                    )
                    expired_ids.append(key)
        return tuple(expired_ids)

    async def close(self) -> None:
        """Clear the store."""
        async with self._lock:
            self._rows.clear()
