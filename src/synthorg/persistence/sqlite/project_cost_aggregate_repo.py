"""SQLite repository for durable project cost aggregates."""

import asyncio
import math
import sqlite3
from datetime import UTC, datetime

import aiosqlite
from pydantic import ValidationError

from synthorg.budget.project_cost_aggregate import ProjectCostAggregate
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.persistence import (
    PERSISTENCE_PROJECT_COST_AGG_DESERIALIZE_FAILED,
    PERSISTENCE_PROJECT_COST_AGG_FETCH_FAILED,
    PERSISTENCE_PROJECT_COST_AGG_FETCHED,
    PERSISTENCE_PROJECT_COST_AGG_INCREMENT_FAILED,
    PERSISTENCE_PROJECT_COST_AGG_INCREMENTED,
)
from synthorg.persistence.errors import QueryError

logger = get_logger(__name__)

_UPSERT_SQL = """\
INSERT INTO project_cost_aggregates
    (project_id, total_cost, total_input_tokens,
     total_output_tokens, record_count, last_updated)
VALUES (?, ?, ?, ?, 1, ?)
ON CONFLICT(project_id) DO UPDATE SET
    total_cost = total_cost + excluded.total_cost,
    total_input_tokens = total_input_tokens + excluded.total_input_tokens,
    total_output_tokens = total_output_tokens + excluded.total_output_tokens,
    record_count = record_count + 1,
    last_updated = excluded.last_updated
RETURNING project_id, total_cost, total_input_tokens,
          total_output_tokens, record_count, last_updated
"""

_SELECT_SQL = """\
SELECT project_id, total_cost, total_input_tokens,
       total_output_tokens, record_count, last_updated
FROM project_cost_aggregates
WHERE project_id = ?
"""


def _row_to_aggregate(row: aiosqlite.Row) -> ProjectCostAggregate:
    """Reconstruct a ``ProjectCostAggregate`` from a database row.

    Args:
        row: A single database row.

    Returns:
        Validated model instance.

    Raises:
        ValidationError: If the row data fails Pydantic validation.
    """
    data = dict(row)
    return ProjectCostAggregate.model_validate(data)


class SQLiteProjectCostAggregateRepository:
    """SQLite-backed project cost aggregate repository.

    Provides atomic increment and lookup for per-project lifetime
    cost totals.  Uses ``INSERT ... ON CONFLICT DO UPDATE`` for
    atomic upsert semantics.

    Args:
        db: An open aiosqlite connection with ``row_factory``
            set to ``aiosqlite.Row``.
        write_lock: Optional shared write lock for serialising
            multi-statement write operations.
    """

    def __init__(
        self,
        db: aiosqlite.Connection,
        *,
        write_lock: asyncio.Lock | None = None,
    ) -> None:
        self._db = db
        self._write_lock = write_lock if write_lock is not None else asyncio.Lock()

    async def get(
        self,
        project_id: NotBlankStr,
    ) -> ProjectCostAggregate | None:
        """Retrieve the aggregate for a project.

        Args:
            project_id: Project identifier.

        Returns:
            The aggregate, or ``None`` if no costs recorded.

        Raises:
            QueryError: If the database operation fails.
        """
        try:
            cursor = await self._db.execute(_SELECT_SQL, (project_id,))
            row = await cursor.fetchone()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            logger.exception(
                PERSISTENCE_PROJECT_COST_AGG_FETCH_FAILED,
                project_id=project_id,
                error=str(exc),
            )
            msg = f"Failed to fetch project cost aggregate for {project_id!r}: {exc}"
            raise QueryError(msg) from exc

        if row is None:
            logger.debug(
                PERSISTENCE_PROJECT_COST_AGG_FETCHED,
                project_id=project_id,
                found=False,
            )
            return None

        try:
            aggregate = _row_to_aggregate(row)
        except ValidationError as exc:
            logger.exception(
                PERSISTENCE_PROJECT_COST_AGG_DESERIALIZE_FAILED,
                project_id=project_id,
                error=str(exc),
            )
            msg = (
                f"Failed to deserialize project cost aggregate"
                f" for {project_id!r}: {exc}"
            )
            raise QueryError(msg) from exc

        logger.debug(
            PERSISTENCE_PROJECT_COST_AGG_FETCHED,
            project_id=project_id,
            found=True,
            total_cost=aggregate.total_cost,
            record_count=aggregate.record_count,
        )
        return aggregate

    async def increment(
        self,
        project_id: NotBlankStr,
        cost: float,
        input_tokens: int,
        output_tokens: int,
    ) -> ProjectCostAggregate:
        """Atomically increment the project's cost aggregate.

        Creates a new row on first call; increments on subsequent.
        Uses ``RETURNING`` to read back the updated row inside the
        same locked section, avoiding race conditions with concurrent
        increments.

        Args:
            project_id: Project identifier.
            cost: Cost delta to add (must be finite and >= 0).
            input_tokens: Input token delta (must be >= 0).
            output_tokens: Output token delta (must be >= 0).

        Returns:
            The updated aggregate after the increment.

        Raises:
            QueryError: If the database operation fails.
            ValueError: If any delta is negative or cost is
                non-finite (NaN/Inf).
        """
        if not math.isfinite(cost) or cost < 0 or input_tokens < 0 or output_tokens < 0:
            msg = (
                "Deltas must be finite and non-negative: "
                f"cost={cost}, input_tokens={input_tokens}, "
                f"output_tokens={output_tokens}"
            )
            logger.warning(
                PERSISTENCE_PROJECT_COST_AGG_INCREMENT_FAILED,
                project_id=project_id,
                cost=cost,
                error=msg,
            )
            raise ValueError(msg)

        now = datetime.now(UTC).isoformat()
        try:
            async with self._write_lock:
                cursor = await self._db.execute(
                    _UPSERT_SQL,
                    (project_id, cost, input_tokens, output_tokens, now),
                )
                row = await cursor.fetchone()
                await self._db.commit()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            logger.exception(
                PERSISTENCE_PROJECT_COST_AGG_INCREMENT_FAILED,
                project_id=project_id,
                cost=cost,
                error=str(exc),
            )
            msg = (
                f"Failed to increment project cost aggregate for {project_id!r}: {exc}"
            )
            raise QueryError(msg) from exc

        if row is None:  # pragma: no cover -- defensive
            msg = f"Aggregate for {project_id!r} missing after upsert"
            raise QueryError(msg)

        try:
            aggregate = _row_to_aggregate(row)
        except ValidationError as exc:
            logger.exception(
                PERSISTENCE_PROJECT_COST_AGG_DESERIALIZE_FAILED,
                project_id=project_id,
                error=str(exc),
            )
            msg = (
                f"Failed to deserialize project cost aggregate"
                f" for {project_id!r} after increment: {exc}"
            )
            raise QueryError(msg) from exc

        logger.debug(
            PERSISTENCE_PROJECT_COST_AGG_INCREMENTED,
            project_id=project_id,
            cost_delta=cost,
            total_cost=aggregate.total_cost,
            record_count=aggregate.record_count,
        )
        return aggregate
