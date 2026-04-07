"""In-memory store for coordination metrics records.

Stores timestamped :class:`CoordinationMetrics` snapshots from
completed multi-agent coordination runs and supports filtered
queries for the ``GET /coordination/metrics`` endpoint.
"""

from collections import deque

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from synthorg.budget.coordination_metrics import CoordinationMetrics  # noqa: TC001
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.coordination_metrics import (
    COORD_METRICS_COLLECTION_COMPLETED,
)

logger = get_logger(__name__)


class CoordinationMetricsRecord(BaseModel):
    """Timestamped coordination metrics from a single run."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    task_id: NotBlankStr = Field(description="Associated task")
    agent_id: NotBlankStr | None = Field(
        default=None,
        description="Lead agent (None for system-level runs)",
    )
    computed_at: AwareDatetime = Field(
        description="When metrics were collected",
    )
    team_size: int = Field(gt=0, description="Coordinating agents")
    metrics: CoordinationMetrics = Field(
        description="All nine Kim et al. metrics (None when skipped)",
    )


class CoordinationMetricsStore:
    """In-memory ring-buffer store for coordination metrics.

    Follows the same eviction pattern as
    :class:`~synthorg.security.audit.AuditLog`.

    Args:
        max_entries: Maximum records retained (oldest evicted first).

    Raises:
        ValueError: If *max_entries* < 1.
    """

    def __init__(self, *, max_entries: int = 10_000) -> None:
        if max_entries < 1:
            msg = f"max_entries must be >= 1, got {max_entries}"
            raise ValueError(msg)
        self._max_entries = max_entries
        self._records: deque[CoordinationMetricsRecord] = deque(
            maxlen=max_entries,
        )

    def record(self, entry: CoordinationMetricsRecord) -> None:
        """Append a metrics record (oldest evicted when full)."""
        self._records.append(entry)
        logger.debug(
            COORD_METRICS_COLLECTION_COMPLETED,
            task_id=entry.task_id,
            agent_id=entry.agent_id,
            team_size=entry.team_size,
        )

    def query(
        self,
        *,
        task_id: str | None = None,
        agent_id: str | None = None,
        since: AwareDatetime | None = None,
        until: AwareDatetime | None = None,
    ) -> tuple[CoordinationMetricsRecord, ...]:
        """Query records with optional AND-combined filters.

        Args:
            task_id: Filter by task identifier.
            agent_id: Filter by lead agent identifier.
            since: Exclude records before this datetime.
            until: Exclude records after this datetime.

        Returns:
            Matching records, newest first.
        """
        results: list[CoordinationMetricsRecord] = []
        for rec in reversed(self._records):
            if task_id is not None and rec.task_id != task_id:
                continue
            if agent_id is not None and rec.agent_id != agent_id:
                continue
            if since is not None and rec.computed_at < since:
                continue
            if until is not None and rec.computed_at > until:
                continue
            results.append(rec)
        return tuple(results)

    def count(self) -> int:
        """Return the number of stored records."""
        return len(self._records)
