"""Postgres repository implementation for security audit entries."""

import json
from datetime import UTC
from typing import TYPE_CHECKING

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import ValidationError

from synthorg.observability import get_logger
from synthorg.observability.events.persistence import (
    PERSISTENCE_AUDIT_ENTRY_DESERIALIZE_FAILED,
    PERSISTENCE_AUDIT_ENTRY_QUERIED,
    PERSISTENCE_AUDIT_ENTRY_QUERY_FAILED,
    PERSISTENCE_AUDIT_ENTRY_SAVE_FAILED,
    PERSISTENCE_AUDIT_ENTRY_SAVED,
)
from synthorg.persistence.errors import DuplicateRecordError, QueryError
from synthorg.security.models import AuditEntry

if TYPE_CHECKING:
    from psycopg_pool import AsyncConnectionPool
    from pydantic import AwareDatetime

    from synthorg.core.enums import ApprovalRiskLevel
    from synthorg.core.types import NotBlankStr
    from synthorg.security.models import AuditVerdictStr

logger = get_logger(__name__)

_COLS = (
    "id, timestamp, agent_id, task_id, tool_name, "
    "tool_category, action_type, arguments_hash, verdict, "
    "risk_level, reason, matched_rules, "
    "evaluation_duration_ms, approval_id"
)


class PostgresAuditRepository:
    """Postgres implementation of the AuditRepository protocol.

    Append-only: entries can be saved and queried, but never updated
    or deleted, preserving audit integrity.

    Timestamps are normalized to UTC to ensure correct ordering in
    TIMESTAMPTZ columns.

    Args:
        pool: An open psycopg_pool.AsyncConnectionPool.
    """

    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def save(self, entry: AuditEntry) -> None:
        """Persist an audit entry (append-only, no upsert).

        Args:
            entry: The audit entry to persist.

        Raises:
            DuplicateRecordError: If an entry with the same ID exists.
            QueryError: If the operation fails.
        """
        try:
            data = entry.model_dump(mode="json")
            # Normalize timestamp to UTC for consistent ordering.
            utc_ts = entry.timestamp.astimezone(UTC)
            async with self._pool.connection() as conn, conn.cursor() as cur:
                await cur.execute(
                    """\
INSERT INTO audit_entries (
    id, timestamp, agent_id, task_id, tool_name, tool_category,
    action_type, arguments_hash, verdict, risk_level, reason,
    matched_rules, evaluation_duration_ms, approval_id
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
)""",
                    (
                        data["id"],
                        utc_ts,
                        data["agent_id"],
                        data["task_id"],
                        data["tool_name"],
                        data["tool_category"],
                        data["action_type"],
                        data["arguments_hash"],
                        data["verdict"],
                        data["risk_level"],
                        data["reason"],
                        Jsonb(list(data["matched_rules"])),
                        data["evaluation_duration_ms"],
                        data["approval_id"],
                    ),
                )
                await conn.commit()
        except psycopg.errors.UniqueViolation as exc:
            msg = f"Duplicate audit entry {entry.id!r}"
            logger.warning(
                PERSISTENCE_AUDIT_ENTRY_SAVE_FAILED,
                entry_id=entry.id,
                error=str(exc),
            )
            raise DuplicateRecordError(msg) from exc
        except psycopg.Error as exc:
            msg = f"Failed to save audit entry {entry.id!r}"
            logger.exception(
                PERSISTENCE_AUDIT_ENTRY_SAVE_FAILED,
                entry_id=entry.id,
                error=str(exc),
            )
            raise QueryError(msg) from exc
        logger.info(
            PERSISTENCE_AUDIT_ENTRY_SAVED,
            entry_id=entry.id,
            agent_id=entry.agent_id,
        )

    async def query(  # noqa: PLR0913
        self,
        *,
        agent_id: NotBlankStr | None = None,
        action_type: str | None = None,
        verdict: AuditVerdictStr | None = None,
        risk_level: ApprovalRiskLevel | None = None,
        since: AwareDatetime | None = None,
        until: AwareDatetime | None = None,
        limit: int = 100,
    ) -> tuple[AuditEntry, ...]:
        """Query audit entries with optional filters (newest first).

        Filters are AND-combined. Results ordered by timestamp
        descending.

        Args:
            agent_id: Filter by agent identifier.
            action_type: Filter by action type string.
            verdict: Filter by verdict string.
            risk_level: Filter by risk level.
            since: Only return entries at or after this timestamp.
            until: Only return entries at or before this timestamp.
            limit: Maximum number of entries (must be >= 1).

        Returns:
            Matching audit entries as a tuple.

        Raises:
            QueryError: If the operation fails, *limit* < 1, or
                *until* is earlier than *since*.
        """
        self._validate_query_args(since=since, until=until, limit=limit)

        where, params = self._build_query_clause(
            agent_id=agent_id,
            action_type=action_type,
            verdict=verdict,
            risk_level=risk_level,
            since=since,
            until=until,
        )
        sql = (
            f"SELECT {_COLS} FROM audit_entries{where} "  # noqa: S608
            "ORDER BY timestamp DESC LIMIT %s"
        )
        params.append(limit)

        try:
            async with (
                self._pool.connection() as conn,
                conn.cursor(row_factory=dict_row) as cur,
            ):
                await cur.execute(sql, params)
                rows = await cur.fetchall()
        except psycopg.Error as exc:
            msg = "Failed to query audit entries"
            logger.exception(
                PERSISTENCE_AUDIT_ENTRY_QUERY_FAILED,
                error=str(exc),
                agent_id=agent_id,
                action_type=action_type,
                verdict=verdict,
                risk_level=(risk_level.value if risk_level else None),
                since=since.isoformat() if since else None,
                until=until.isoformat() if until else None,
                limit=limit,
            )
            raise QueryError(msg) from exc

        results = tuple(self._row_to_entry(row) for row in rows)
        logger.debug(
            PERSISTENCE_AUDIT_ENTRY_QUERIED,
            count=len(results),
        )
        return results

    def _validate_query_args(
        self,
        *,
        since: AwareDatetime | None,
        until: AwareDatetime | None,
        limit: int,
    ) -> None:
        """Validate query parameters before execution.

        Raises:
            QueryError: If *limit* < 1 or *until* < *since*.
        """
        if limit < 1:
            msg = f"limit must be >= 1, got {limit}"
            logger.warning(
                PERSISTENCE_AUDIT_ENTRY_QUERY_FAILED,
                error=msg,
                limit=limit,
            )
            raise QueryError(msg)

        if since is not None and until is not None and until < since:
            msg = "until must not be earlier than since"
            logger.warning(
                PERSISTENCE_AUDIT_ENTRY_QUERY_FAILED,
                error=msg,
                since=since.isoformat(),
                until=until.isoformat(),
            )
            raise QueryError(msg)

    def _build_query_clause(  # noqa: PLR0913
        self,
        *,
        agent_id: NotBlankStr | None,
        action_type: str | None,
        verdict: AuditVerdictStr | None,
        risk_level: ApprovalRiskLevel | None,
        since: AwareDatetime | None,
        until: AwareDatetime | None,
    ) -> tuple[str, list[object]]:
        """Build WHERE clause and parameters for audit query.

        Timestamps are normalized to UTC for consistent comparison.

        Returns:
            Tuple of (WHERE clause string, parameter list).
        """
        conditions: list[str] = []
        params: list[object] = []

        if agent_id is not None:
            conditions.append("agent_id = %s")
            params.append(agent_id)
        if action_type is not None:
            conditions.append("action_type = %s")
            params.append(action_type)
        if verdict is not None:
            conditions.append("verdict = %s")
            params.append(verdict)
        if risk_level is not None:
            conditions.append("risk_level = %s")
            params.append(risk_level.value)
        if since is not None:
            conditions.append("timestamp >= %s")
            params.append(since.astimezone(UTC))
        if until is not None:
            conditions.append("timestamp <= %s")
            params.append(until.astimezone(UTC))

        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        return where, params

    def _row_to_entry(self, row: dict[str, object]) -> AuditEntry:
        """Convert a database row to an ``AuditEntry`` model.

        Args:
            row: A dict mapping column names to their values.

        Raises:
            QueryError: If the row cannot be deserialized.
        """
        try:
            raw_rules = row.get("matched_rules")
            # In Postgres, JSONB comes back as dict/list, not string
            if isinstance(raw_rules, str):
                # Shouldn't happen with JSONB, but be defensive
                parsed = {**row, "matched_rules": json.loads(raw_rules)}
            else:
                parsed = row
            return AuditEntry.model_validate(parsed)
        except (ValidationError, KeyError, TypeError, json.JSONDecodeError) as exc:
            msg = f"Failed to deserialize audit entry {row.get('id')!r}"
            logger.exception(
                PERSISTENCE_AUDIT_ENTRY_DESERIALIZE_FAILED,
                entry_id=row.get("id"),
                error=str(exc),
            )
            raise QueryError(msg) from exc
