"""In-memory, append-only tool invocation tracker.

Records :class:`ToolInvocationRecord` entries from tool executions and
provides filtered queries for the activity timeline.
"""

import asyncio
from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.tool import (
    TOOL_INVOCATION_RECORDED,
    TOOL_INVOCATIONS_QUERIED,
)

if TYPE_CHECKING:
    from datetime import datetime

    from synthorg.tools.invocation_record import ToolInvocationRecord

logger = get_logger(__name__)


class ToolInvocationTracker:
    """In-memory, append-only tool invocation tracking service.

    Records tool invocation outcomes and provides filtered queries
    for the activity timeline.
    """

    def __init__(self) -> None:
        self._records: list[ToolInvocationRecord] = []
        self._lock: asyncio.Lock = asyncio.Lock()

    async def record(self, invocation: ToolInvocationRecord) -> None:
        """Append a tool invocation record.

        Args:
            invocation: Immutable invocation record to store.
        """
        async with self._lock:
            self._records.append(invocation)
            logger.debug(
                TOOL_INVOCATION_RECORDED,
                agent_id=invocation.agent_id,
                tool_name=invocation.tool_name,
                is_success=invocation.is_success,
            )

    async def get_records(
        self,
        *,
        agent_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> tuple[ToolInvocationRecord, ...]:
        """Return filtered tool invocation records.

        Time semantics: ``start <= timestamp < end``.

        Args:
            agent_id: Filter by agent.
            start: Inclusive lower bound on ``timestamp``.
            end: Exclusive upper bound on ``timestamp``.

        Returns:
            Immutable tuple of matching records.

        Raises:
            ValueError: If both *start* and *end* are given and
                ``start >= end``.
        """
        if start is not None and end is not None and start >= end:
            msg = f"start ({start.isoformat()}) must be before end ({end.isoformat()})"
            raise ValueError(msg)
        logger.debug(
            TOOL_INVOCATIONS_QUERIED,
            agent_id=agent_id,
            start=start,
            end=end,
        )
        async with self._lock:
            snapshot = tuple(self._records)
        return tuple(
            r
            for r in snapshot
            if (agent_id is None or r.agent_id == agent_id)
            and (start is None or r.timestamp >= start)
            and (end is None or r.timestamp < end)
        )
