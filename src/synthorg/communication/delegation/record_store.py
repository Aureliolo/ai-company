"""In-memory, append-only delegation record store.

Stores :class:`DelegationRecord` entries from delegation operations and
provides filtered queries for the activity timeline.  When the record
count exceeds ``max_records``, oldest entries are evicted (FIFO).
"""

import asyncio
from collections import deque
from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.delegation import (
    DELEGATION_RECORD_EVICTED,
    DELEGATION_RECORD_STORED,
    DELEGATION_RECORDS_QUERIED,
)

if TYPE_CHECKING:
    from datetime import datetime

    from synthorg.communication.delegation.models import DelegationRecord

logger = get_logger(__name__)

_DEFAULT_MAX_RECORDS = 10_000


class DelegationRecordStore:
    """In-memory, append-only delegation record store with filtering.

    Provides both a sync ``record_sync`` method (for callers that
    cannot await) and async query methods.  When record count exceeds
    ``max_records``, oldest entries are evicted (FIFO).

    Concurrency note: ``record_sync`` does not acquire ``_lock``.
    The lock serialises concurrent async readers only.  Append-only
    semantics and cooperative asyncio scheduling make single-call
    sync writes safe (``deque.append`` cannot be interrupted).

    Args:
        max_records: Maximum records before oldest are evicted.

    Raises:
        ValueError: If *max_records* < 1.
    """

    def __init__(
        self,
        *,
        max_records: int = _DEFAULT_MAX_RECORDS,
    ) -> None:
        if max_records < 1:
            msg = f"max_records must be >= 1, got {max_records}"
            raise ValueError(msg)
        self._records: deque[DelegationRecord] = deque(
            maxlen=max_records,
        )
        self._lock: asyncio.Lock = asyncio.Lock()

    def record_sync(self, delegation: DelegationRecord) -> None:
        """Append a delegation record (sync, for cooperative scheduling).

        Safe to call from sync code under asyncio cooperative scheduling
        since a plain deque append cannot be interrupted by another
        coroutine.

        Args:
            delegation: Immutable delegation record to store.
        """
        if len(self._records) == self._records.maxlen:
            logger.warning(
                DELEGATION_RECORD_EVICTED,
                max_records=self._records.maxlen,
            )
        self._records.append(delegation)
        logger.debug(
            DELEGATION_RECORD_STORED,
            delegation_id=delegation.delegation_id,
            delegator_id=delegation.delegator_id,
            delegatee_id=delegation.delegatee_id,
        )

    async def get_records_as_delegator(
        self,
        agent_id: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> tuple[DelegationRecord, ...]:
        """Return records where *agent_id* is the delegator (sent).

        Args:
            agent_id: Delegator agent ID.
            start: Inclusive lower bound on ``timestamp``.
            end: Exclusive upper bound on ``timestamp``.

        Returns:
            Matching delegation records.

        Raises:
            ValueError: If both *start* and *end* are given and
                ``start >= end``.
        """
        _validate_time_range(start, end)
        snapshot = await self._snapshot()
        logger.debug(
            DELEGATION_RECORDS_QUERIED,
            perspective="delegator",
            agent_id=agent_id,
        )
        return _filter(snapshot, delegator_id=agent_id, start=start, end=end)

    async def get_records_as_delegatee(
        self,
        agent_id: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> tuple[DelegationRecord, ...]:
        """Return records where *agent_id* is the delegatee (received).

        Args:
            agent_id: Delegatee agent ID.
            start: Inclusive lower bound on ``timestamp``.
            end: Exclusive upper bound on ``timestamp``.

        Returns:
            Matching delegation records.

        Raises:
            ValueError: If both *start* and *end* are given and
                ``start >= end``.
        """
        _validate_time_range(start, end)
        snapshot = await self._snapshot()
        logger.debug(
            DELEGATION_RECORDS_QUERIED,
            perspective="delegatee",
            agent_id=agent_id,
        )
        return _filter(snapshot, delegatee_id=agent_id, start=start, end=end)

    async def get_all_records(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> tuple[DelegationRecord, ...]:
        """Return all records in the given time range.

        Args:
            start: Inclusive lower bound on ``timestamp``.
            end: Exclusive upper bound on ``timestamp``.

        Returns:
            All matching delegation records.

        Raises:
            ValueError: If both *start* and *end* are given and
                ``start >= end``.
        """
        _validate_time_range(start, end)
        snapshot = await self._snapshot()
        logger.debug(DELEGATION_RECORDS_QUERIED, perspective="all")
        return _filter(snapshot, start=start, end=end)

    async def _snapshot(self) -> tuple[DelegationRecord, ...]:
        """Return an immutable snapshot of all current records."""
        async with self._lock:
            return tuple(self._records)


# ── Module-level pure helpers ────────────────────────────────────


def _validate_time_range(
    start: datetime | None,
    end: datetime | None,
) -> None:
    """Raise ``ValueError`` if *start* >= *end* when both are given."""
    if start is not None and end is not None and start >= end:
        msg = f"start ({start.isoformat()}) must be before end ({end.isoformat()})"
        raise ValueError(msg)


def _filter(
    records: tuple[DelegationRecord, ...],
    *,
    delegator_id: str | None = None,
    delegatee_id: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> tuple[DelegationRecord, ...]:
    """Filter records by role and/or time range.

    Time semantics: ``start <= timestamp < end``.
    """
    return tuple(
        r
        for r in records
        if (delegator_id is None or r.delegator_id == delegator_id)
        and (delegatee_id is None or r.delegatee_id == delegatee_id)
        and (start is None or r.timestamp >= start)
        and (end is None or r.timestamp < end)
    )
