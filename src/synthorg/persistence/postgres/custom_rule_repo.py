"""Postgres-backed custom signal rule repository.

Persists :class:`CustomRuleDefinition` rows in the ``custom_rules``
table using the shared ``AsyncConnectionPool``.  Each operation
checks out a connection via ``async with pool.connection() as conn``;
the context manager auto-commits on clean exit.

Read paths use ``psycopg.rows.dict_row`` so row access is by column
name -- robust to accidental SELECT re-ordering.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.meta.models import ProposalAltitude, RuleSeverity
from synthorg.meta.rules.custom import Comparator, CustomRuleDefinition
from synthorg.observability import get_logger, safe_error_description
from synthorg.observability.events.meta import (
    META_CUSTOM_RULE_DELETE_FAILED,
    META_CUSTOM_RULE_FETCH_FAILED,
    META_CUSTOM_RULE_FETCHED,
    META_CUSTOM_RULE_LIST_FAILED,
    META_CUSTOM_RULE_LISTED,
    META_CUSTOM_RULE_SAVE_FAILED,
)
from synthorg.persistence.errors import ConstraintViolationError, QueryError

if TYPE_CHECKING:
    from psycopg_pool import AsyncConnectionPool


logger = get_logger(__name__)


def _ensure_tz(value: datetime) -> datetime:
    """Normalize a ``TIMESTAMPTZ`` round-trip to UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _row_to_definition(row: dict[str, Any]) -> CustomRuleDefinition:
    """Deserialize a dict row into a :class:`CustomRuleDefinition`.

    Raises:
        QueryError: If the row has corrupt or unparseable data.
    """
    try:
        altitudes_raw = row["target_altitudes"]
        return CustomRuleDefinition(
            id=UUID(str(row["id"])),
            name=str(row["name"]),
            description=str(row["description"]),
            metric_path=str(row["metric_path"]),
            comparator=Comparator(str(row["comparator"])),
            threshold=float(row["threshold"]),
            severity=RuleSeverity(str(row["severity"])),
            target_altitudes=tuple(ProposalAltitude(a) for a in altitudes_raw),
            enabled=bool(row["enabled"]),
            created_at=_ensure_tz(row["created_at"]),
            updated_at=_ensure_tz(row["updated_at"]),
        )
    except (ValueError, TypeError, KeyError) as exc:
        row_id = str(row.get("id", "<unknown>")) if row else "<unknown>"
        msg = f"Failed to parse custom rule row {row_id!r}"
        logger.warning(
            META_CUSTOM_RULE_FETCH_FAILED,
            row_id=row_id,
            error_type=type(exc).__name__,
            error=safe_error_description(exc),
        )
        raise QueryError(msg) from exc


class PostgresCustomRuleRepository:
    """Postgres-backed custom signal rule repository.

    Provides CRUD operations for user-defined declarative rules
    against the shared ``AsyncConnectionPool``.

    Args:
        pool: The shared async Postgres connection pool.
    """

    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def save(self, rule: CustomRuleDefinition) -> None:
        """Persist a custom rule via upsert.

        Args:
            rule: The rule definition to persist.

        Raises:
            ConstraintViolationError: If the rule name conflicts
                with a different existing rule.
            QueryError: If the database operation fails.
        """
        altitudes_json = [a.value for a in rule.target_altitudes]
        try:
            async with self._pool.connection() as conn, conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO custom_rules (
                        id, name, description, metric_path,
                        comparator, threshold, severity,
                        target_altitudes, enabled,
                        created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        metric_path = EXCLUDED.metric_path,
                        comparator = EXCLUDED.comparator,
                        threshold = EXCLUDED.threshold,
                        severity = EXCLUDED.severity,
                        target_altitudes = EXCLUDED.target_altitudes,
                        enabled = EXCLUDED.enabled,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        str(rule.id),
                        rule.name,
                        rule.description,
                        rule.metric_path,
                        rule.comparator.value,
                        rule.threshold,
                        rule.severity.value,
                        Jsonb(altitudes_json),
                        rule.enabled,
                        rule.created_at.astimezone(UTC),
                        rule.updated_at.astimezone(UTC),
                    ),
                )
        except psycopg.errors.UniqueViolation as exc:
            constraint_name = getattr(exc.diag, "constraint_name", "") or ""
            if constraint_name == "custom_rules_name":
                msg = f"Custom rule name '{rule.name}' already exists"
                logger.warning(
                    META_CUSTOM_RULE_SAVE_FAILED,
                    rule_name=rule.name,
                    error=msg,
                )
                raise ConstraintViolationError(
                    msg,
                    constraint="custom_rules_name",
                ) from exc
            msg = f"Constraint violation saving custom rule {rule.name!r}"
            logger.warning(
                META_CUSTOM_RULE_SAVE_FAILED,
                rule_name=rule.name,
                error=msg,
                constraint=constraint_name or "unknown",
            )
            raise ConstraintViolationError(
                msg,
                constraint=constraint_name or "custom_rules_unknown",
            ) from exc
        except MemoryError, RecursionError:
            raise
        except psycopg.Error as exc:
            msg = f"Failed to save custom rule {rule.name!r}"
            logger.warning(
                META_CUSTOM_RULE_SAVE_FAILED,
                rule_name=rule.name,
                error_type=type(exc).__name__,
                error=safe_error_description(exc),
            )
            raise QueryError(msg) from exc

    async def get(
        self,
        rule_id: NotBlankStr,
    ) -> CustomRuleDefinition | None:
        """Retrieve a custom rule by id.

        Args:
            rule_id: UUID string of the rule.

        Returns:
            The rule definition, or ``None`` if not found.

        Raises:
            QueryError: If the database query fails.
        """
        try:
            async with (
                self._pool.connection() as conn,
                conn.cursor(row_factory=dict_row) as cur,
            ):
                await cur.execute(
                    """
                    SELECT id, name, description, metric_path,
                           comparator, threshold, severity,
                           target_altitudes, enabled,
                           created_at, updated_at
                    FROM custom_rules WHERE id = %s
                    """,
                    (rule_id,),
                )
                row = await cur.fetchone()
        except MemoryError, RecursionError:
            raise
        except psycopg.Error as exc:
            msg = f"Failed to fetch custom rule {rule_id!r}"
            logger.warning(
                META_CUSTOM_RULE_FETCH_FAILED,
                rule_id=rule_id,
                error_type=type(exc).__name__,
                error=safe_error_description(exc),
            )
            raise QueryError(msg) from exc
        if row is None:
            logger.debug(
                META_CUSTOM_RULE_FETCHED,
                rule_id=rule_id,
                found=False,
            )
            return None
        logger.debug(
            META_CUSTOM_RULE_FETCHED,
            rule_id=rule_id,
            found=True,
        )
        return _row_to_definition(row)

    async def get_by_name(
        self,
        name: NotBlankStr,
    ) -> CustomRuleDefinition | None:
        """Retrieve a custom rule by name.

        Args:
            name: Unique rule name.

        Returns:
            The rule definition, or ``None`` if not found.

        Raises:
            QueryError: If the database query fails.
        """
        try:
            async with (
                self._pool.connection() as conn,
                conn.cursor(row_factory=dict_row) as cur,
            ):
                await cur.execute(
                    """
                    SELECT id, name, description, metric_path,
                           comparator, threshold, severity,
                           target_altitudes, enabled,
                           created_at, updated_at
                    FROM custom_rules WHERE name = %s
                    """,
                    (name,),
                )
                row = await cur.fetchone()
        except MemoryError, RecursionError:
            raise
        except psycopg.Error as exc:
            msg = f"Failed to fetch custom rule by name {name!r}"
            logger.warning(
                META_CUSTOM_RULE_FETCH_FAILED,
                rule_name=name,
                error_type=type(exc).__name__,
                error=safe_error_description(exc),
            )
            raise QueryError(msg) from exc
        if row is None:
            return None
        return _row_to_definition(row)

    async def list_rules(
        self,
        *,
        enabled_only: bool = False,
    ) -> tuple[CustomRuleDefinition, ...]:
        """List custom rules ordered by name.

        Args:
            enabled_only: If ``True``, return only enabled rules.

        Returns:
            Tuple of rule definitions.

        Raises:
            QueryError: If the query fails.
        """
        query = (
            "SELECT id, name, description, metric_path, "
            "comparator, threshold, severity, target_altitudes, "
            "enabled, created_at, updated_at "
            "FROM custom_rules"
        )
        if enabled_only:
            query += " WHERE enabled = true"
        query += " ORDER BY name"
        try:
            async with (
                self._pool.connection() as conn,
                conn.cursor(row_factory=dict_row) as cur,
            ):
                await cur.execute(query)
                rows = await cur.fetchall()
        except MemoryError, RecursionError:
            raise
        except psycopg.Error as exc:
            msg = "Failed to list custom rules"
            logger.warning(
                META_CUSTOM_RULE_LIST_FAILED,
                error_type=type(exc).__name__,
                error=safe_error_description(exc),
            )
            raise QueryError(msg) from exc
        result = tuple(_row_to_definition(row) for row in rows)
        logger.debug(META_CUSTOM_RULE_LISTED, count=len(result))
        return result

    async def delete(self, rule_id: NotBlankStr) -> bool:
        """Delete a custom rule by id.

        Args:
            rule_id: UUID string of the rule.

        Returns:
            ``True`` if a row was deleted, ``False`` if not found.

        Raises:
            QueryError: If the operation fails.
        """
        try:
            async with self._pool.connection() as conn, conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM custom_rules WHERE id = %s",
                    (rule_id,),
                )
                deleted = cur.rowcount > 0
        except MemoryError, RecursionError:
            raise
        except psycopg.Error as exc:
            msg = f"Failed to delete custom rule {rule_id!r}"
            logger.warning(
                META_CUSTOM_RULE_DELETE_FAILED,
                rule_id=rule_id,
                error_type=type(exc).__name__,
                error=safe_error_description(exc),
            )
            raise QueryError(msg) from exc
        return deleted
