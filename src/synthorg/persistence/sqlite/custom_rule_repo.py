"""SQLite repository implementation for custom signal rules."""

import json
import sqlite3
from datetime import datetime
from uuid import UUID

import aiosqlite  # noqa: TC002
from aiosqlite import Row  # noqa: TC002

from synthorg.core.types import NotBlankStr  # noqa: TC001
from synthorg.meta.models import ProposalAltitude, RuleSeverity
from synthorg.meta.rules.custom import Comparator, CustomRuleDefinition
from synthorg.observability import get_logger
from synthorg.observability.events.meta import (
    META_CUSTOM_RULE_DELETE_FAILED,
    META_CUSTOM_RULE_DELETED,
    META_CUSTOM_RULE_FETCH_FAILED,
    META_CUSTOM_RULE_FETCHED,
    META_CUSTOM_RULE_LIST_FAILED,
    META_CUSTOM_RULE_LISTED,
    META_CUSTOM_RULE_SAVE_FAILED,
    META_CUSTOM_RULE_SAVED,
)
from synthorg.persistence.errors import ConstraintViolationError, QueryError

logger = get_logger(__name__)


def _row_to_definition(row: Row) -> CustomRuleDefinition:
    """Convert a database row to a CustomRuleDefinition.

    Raises:
        QueryError: If the row contains corrupt or unparseable data.
    """
    try:
        altitudes_raw: list[str] = json.loads(str(row[7]))
        return CustomRuleDefinition(
            id=UUID(str(row[0])),
            name=str(row[1]),
            description=str(row[2]),
            metric_path=str(row[3]),
            comparator=Comparator(str(row[4])),
            threshold=float(str(row[5])),
            severity=RuleSeverity(str(row[6])),
            target_altitudes=tuple(ProposalAltitude(a) for a in altitudes_raw),
            enabled=bool(row[8]),
            created_at=datetime.fromisoformat(str(row[9])),
            updated_at=datetime.fromisoformat(str(row[10])),
        )
    except (json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
        row_id = str(row[0]) if row else "<unknown>"
        msg = f"Failed to parse custom rule row {row_id!r}: {exc}"
        logger.exception(
            META_CUSTOM_RULE_FETCH_FAILED,
            row_id=row_id,
            error=msg,
        )
        raise QueryError(msg) from exc


class SQLiteCustomRuleRepository:
    """SQLite-backed custom signal rule repository.

    Provides CRUD operations for user-defined declarative rules
    using a shared ``aiosqlite.Connection``.

    Args:
        db: An open aiosqlite connection.
    """

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def save(self, rule: CustomRuleDefinition) -> None:
        """Persist a custom rule via upsert.

        Args:
            rule: The rule definition to persist.

        Raises:
            ConstraintViolationError: If the rule name conflicts
                with a different existing rule.
            QueryError: If the database operation fails.
        """
        altitudes_json = json.dumps(
            [a.value for a in rule.target_altitudes],
        )
        try:
            await self._db.execute(
                """\
INSERT INTO custom_rules (id, name, description, metric_path,
                         comparator, threshold, severity,
                         target_altitudes, enabled,
                         created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(id) DO UPDATE SET
    name=excluded.name,
    description=excluded.description,
    metric_path=excluded.metric_path,
    comparator=excluded.comparator,
    threshold=excluded.threshold,
    severity=excluded.severity,
    target_altitudes=excluded.target_altitudes,
    enabled=excluded.enabled,
    updated_at=excluded.updated_at""",
                (
                    str(rule.id),
                    rule.name,
                    rule.description,
                    rule.metric_path,
                    rule.comparator.value,
                    rule.threshold,
                    rule.severity.value,
                    altitudes_json,
                    int(rule.enabled),
                    rule.created_at.isoformat(),
                    rule.updated_at.isoformat(),
                ),
            )
            await self._db.commit()
        except sqlite3.IntegrityError as exc:
            await self._db.rollback()
            err_msg = str(exc).lower()
            if "unique" in err_msg and "name" in err_msg:
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
            )
            raise ConstraintViolationError(
                msg,
                constraint="custom_rules_unknown",
            ) from exc
        except sqlite3.Error as exc:
            await self._db.rollback()
            msg = f"Failed to save custom rule {rule.name!r}"
            logger.exception(
                META_CUSTOM_RULE_SAVE_FAILED,
                rule_name=rule.name,
                error=str(exc),
            )
            raise QueryError(msg) from exc
        logger.info(
            META_CUSTOM_RULE_SAVED,
            rule_id=str(rule.id),
            rule_name=rule.name,
        )

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
            async with self._db.execute(
                "SELECT id, name, description, metric_path, "
                "comparator, threshold, severity, target_altitudes, "
                "enabled, created_at, updated_at "
                "FROM custom_rules WHERE id = ?",
                (rule_id,),
            ) as cursor:
                row = await cursor.fetchone()
        except sqlite3.Error as exc:
            msg = f"Failed to fetch custom rule {rule_id!r}"
            logger.exception(
                META_CUSTOM_RULE_FETCH_FAILED,
                rule_id=rule_id,
                error=str(exc),
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
            async with self._db.execute(
                "SELECT id, name, description, metric_path, "
                "comparator, threshold, severity, target_altitudes, "
                "enabled, created_at, updated_at "
                "FROM custom_rules WHERE name = ?",
                (name,),
            ) as cursor:
                row = await cursor.fetchone()
        except sqlite3.Error as exc:
            msg = f"Failed to fetch custom rule by name {name!r}"
            logger.exception(
                META_CUSTOM_RULE_FETCH_FAILED,
                rule_name=name,
                error=str(exc),
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
            query += " WHERE enabled = 1"
        query += " ORDER BY name"
        try:
            async with self._db.execute(query) as cursor:
                rows = await cursor.fetchall()
        except sqlite3.Error as exc:
            msg = "Failed to list custom rules"
            logger.exception(
                META_CUSTOM_RULE_LIST_FAILED,
                error=str(exc),
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
            async with self._db.execute(
                "DELETE FROM custom_rules WHERE id = ?",
                (rule_id,),
            ) as cursor:
                deleted = cursor.rowcount > 0
            await self._db.commit()
        except sqlite3.Error as exc:
            await self._db.rollback()
            msg = f"Failed to delete custom rule {rule_id!r}"
            logger.exception(
                META_CUSTOM_RULE_DELETE_FAILED,
                rule_id=rule_id,
                error=str(exc),
            )
            raise QueryError(msg) from exc
        logger.info(
            META_CUSTOM_RULE_DELETED,
            rule_id=rule_id,
            deleted=deleted,
        )
        return deleted
