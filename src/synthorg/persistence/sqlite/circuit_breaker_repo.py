"""SQLite repository for circuit breaker state persistence."""

import sqlite3

import aiosqlite
from pydantic import ValidationError

from synthorg.observability import get_logger
from synthorg.observability.events.persistence import (
    PERSISTENCE_CIRCUIT_BREAKER_DELETE_FAILED,
    PERSISTENCE_CIRCUIT_BREAKER_DELETED,
    PERSISTENCE_CIRCUIT_BREAKER_LOAD_FAILED,
    PERSISTENCE_CIRCUIT_BREAKER_LOADED,
    PERSISTENCE_CIRCUIT_BREAKER_SAVE_FAILED,
    PERSISTENCE_CIRCUIT_BREAKER_SAVED,
)
from synthorg.persistence.circuit_breaker_repo import (
    CircuitBreakerStateRecord,
)
from synthorg.persistence.errors import QueryError

logger = get_logger(__name__)


class SQLiteCircuitBreakerStateRepository:
    """SQLite implementation of the CircuitBreakerStateRepository protocol.

    Args:
        db: An open aiosqlite connection.
    """

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def save(self, record: CircuitBreakerStateRecord) -> None:
        """Persist a circuit breaker state record (upsert by pair key)."""
        try:
            await self._db.execute(
                """\
INSERT OR REPLACE INTO circuit_breaker_state (
    pair_key_a, pair_key_b, bounce_count, trip_count, opened_at
) VALUES (
    :pair_key_a, :pair_key_b, :bounce_count, :trip_count, :opened_at
)""",
                record.model_dump(mode="json"),
            )
            await self._db.commit()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = (
                f"Failed to save circuit breaker state for pair "
                f"({record.pair_key_a!r}, {record.pair_key_b!r})"
            )
            logger.exception(
                PERSISTENCE_CIRCUIT_BREAKER_SAVE_FAILED,
                pair_key_a=record.pair_key_a,
                pair_key_b=record.pair_key_b,
                error=str(exc),
            )
            raise QueryError(msg) from exc
        logger.debug(
            PERSISTENCE_CIRCUIT_BREAKER_SAVED,
            pair_key_a=record.pair_key_a,
            pair_key_b=record.pair_key_b,
        )

    async def load_all(self) -> tuple[CircuitBreakerStateRecord, ...]:
        """Load all persisted circuit breaker state records."""
        try:
            cursor = await self._db.execute(
                "SELECT pair_key_a, pair_key_b, bounce_count, "
                "trip_count, opened_at FROM circuit_breaker_state",
            )
            rows = await cursor.fetchall()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = "Failed to load circuit breaker state"
            logger.exception(
                PERSISTENCE_CIRCUIT_BREAKER_LOAD_FAILED,
                error=str(exc),
            )
            raise QueryError(msg) from exc

        results: list[CircuitBreakerStateRecord] = []
        for row in rows:
            try:
                results.append(
                    CircuitBreakerStateRecord.model_validate(dict(row)),
                )
            except ValidationError:
                logger.exception(
                    PERSISTENCE_CIRCUIT_BREAKER_LOAD_FAILED,
                    pair_key_a=row["pair_key_a"] if row else "unknown",
                    note="deserialization failed",
                )
        logger.debug(
            PERSISTENCE_CIRCUIT_BREAKER_LOADED,
            count=len(results),
        )
        return tuple(results)

    async def delete(self, pair_key_a: str, pair_key_b: str) -> bool:
        """Delete a circuit breaker state record."""
        try:
            cursor = await self._db.execute(
                "DELETE FROM circuit_breaker_state "
                "WHERE pair_key_a = ? AND pair_key_b = ?",
                (pair_key_a, pair_key_b),
            )
            deleted = cursor.rowcount > 0
            await self._db.commit()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = (
                f"Failed to delete circuit breaker state for pair "
                f"({pair_key_a!r}, {pair_key_b!r})"
            )
            logger.exception(
                PERSISTENCE_CIRCUIT_BREAKER_DELETE_FAILED,
                pair_key_a=pair_key_a,
                pair_key_b=pair_key_b,
                error=str(exc),
            )
            raise QueryError(msg) from exc
        if deleted:
            logger.debug(
                PERSISTENCE_CIRCUIT_BREAKER_DELETED,
                pair_key_a=pair_key_a,
                pair_key_b=pair_key_b,
            )
        return deleted
