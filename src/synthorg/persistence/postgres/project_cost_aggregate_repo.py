"""Postgres implementation of the ProjectCostAggregateRepository protocol.

This is the Postgres sibling of
src/synthorg/persistence/sqlite/project_cost_aggregate_repo.py.
Postgres stores total_cost and token counts as native numeric types.
"""

import math
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import psycopg
from psycopg.rows import dict_row
from pydantic import ValidationError

from synthorg.budget.project_cost_aggregate import ProjectCostAggregate
from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.observability import get_logger, safe_error_description
from synthorg.observability.events.persistence import (
    PERSISTENCE_PROJECT_COST_AGG_DESERIALIZE_FAILED,
    PERSISTENCE_PROJECT_COST_AGG_FETCH_FAILED,
    PERSISTENCE_PROJECT_COST_AGG_FETCHED,
    PERSISTENCE_PROJECT_COST_AGG_INCREMENT_FAILED,
    PERSISTENCE_PROJECT_COST_AGG_INCREMENTED,
)
from synthorg.persistence.errors import QueryError

if TYPE_CHECKING:
    from psycopg_pool import AsyncConnectionPool

logger = get_logger(__name__)

_UPSERT_SQL = """\
INSERT INTO project_cost_aggregates
    (project_id, total_cost, total_input_tokens,
     total_output_tokens, record_count, last_updated)
VALUES (%s, %s, %s, %s, 1, %s)
ON CONFLICT(project_id) DO UPDATE SET
    total_cost = project_cost_aggregates.total_cost + EXCLUDED.total_cost,
    total_input_tokens = project_cost_aggregates.total_input_tokens
        + EXCLUDED.total_input_tokens,
    total_output_tokens = project_cost_aggregates.total_output_tokens
        + EXCLUDED.total_output_tokens,
    record_count = project_cost_aggregates.record_count + 1,
    last_updated = EXCLUDED.last_updated
RETURNING project_id, total_cost, total_input_tokens,
          total_output_tokens, record_count, last_updated
"""

_SELECT_SQL = """\
SELECT project_id, total_cost, total_input_tokens,
       total_output_tokens, record_count, last_updated
FROM project_cost_aggregates
WHERE project_id = %s
"""


class PostgresProjectCostAggregateRepository:
    """Postgres-backed project cost aggregate repository.

    Provides atomic increment and lookup for per-project lifetime
    cost totals.  Uses ``INSERT ... ON CONFLICT DO UPDATE`` for
    atomic upsert semantics.

    Args:
        pool: An open psycopg_pool.AsyncConnectionPool.
    """

    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    @staticmethod
    def _deserialize(
        row: dict[str, object],
        project_id: NotBlankStr,
        *,
        context: str = "",
    ) -> ProjectCostAggregate:
        """Validate a raw row into a ``ProjectCostAggregate``.

        Centralizes the Pydantic validation + ``QueryError`` wrap used
        by both ``get()`` and ``increment()`` so the logging/event
        constant stays consistent.

        Args:
            row: Raw mapping returned by psycopg.
            project_id: Project id (for error context + logging).
            context: Optional suffix describing the call site
                (e.g. ``"after increment"``).

        Raises:
            QueryError: If the row cannot be validated.
        """
        try:
            return ProjectCostAggregate.model_validate(row)
        except ValidationError as exc:
            logger.warning(
                PERSISTENCE_PROJECT_COST_AGG_DESERIALIZE_FAILED,
                project_id=project_id,
                error_type=type(exc).__name__,
                error=safe_error_description(exc),
            )
            suffix = f" {context}" if context else ""
            msg = (
                f"Failed to deserialize project cost aggregate"
                f" for {project_id!r}{suffix}: {exc}"
            )
            raise QueryError(msg) from exc

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
            async with (
                self._pool.connection() as conn,
                conn.cursor(row_factory=dict_row) as cur,
            ):
                await cur.execute(_SELECT_SQL, (project_id,))
                row = await cur.fetchone()
        except psycopg.Error as exc:
            logger.warning(
                PERSISTENCE_PROJECT_COST_AGG_FETCH_FAILED,
                project_id=project_id,
                error_type=type(exc).__name__,
                error=safe_error_description(exc),
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

        aggregate = self._deserialize(row, project_id)

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
        same transaction, avoiding race conditions with concurrent
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

        now = datetime.now(UTC)
        try:
            async with (
                self._pool.connection() as conn,
                conn.cursor(row_factory=dict_row) as cur,
            ):
                await cur.execute(
                    _UPSERT_SQL,
                    (project_id, cost, input_tokens, output_tokens, now),
                )
                row = await cur.fetchone()
                if row is None:  # pragma: no cover -- defensive
                    logger.error(
                        PERSISTENCE_PROJECT_COST_AGG_INCREMENT_FAILED,
                        project_id=project_id,
                        error="RETURNING clause produced no row after upsert",
                    )
                    await conn.rollback()
                    msg = f"Aggregate for {project_id!r} missing after upsert"
                    raise QueryError(msg)
                # Validate BEFORE committing -- if the row can't be
                # deserialized into the domain model, the raw increment
                # must be rolled back so a retry can try again without
                # double-counting.
                aggregate = self._deserialize(
                    row, project_id, context="after increment"
                )
                await conn.commit()
        except psycopg.Error as exc:
            logger.warning(
                PERSISTENCE_PROJECT_COST_AGG_INCREMENT_FAILED,
                project_id=project_id,
                cost=cost,
                error_type=type(exc).__name__,
                error=safe_error_description(exc),
            )
            msg = (
                f"Failed to increment project cost aggregate for {project_id!r}: {exc}"
            )
            raise QueryError(msg) from exc

        logger.info(
            PERSISTENCE_PROJECT_COST_AGG_INCREMENTED,
            project_id=project_id,
            cost_delta=cost,
            total_cost=aggregate.total_cost,
            record_count=aggregate.record_count,
        )
        return aggregate
