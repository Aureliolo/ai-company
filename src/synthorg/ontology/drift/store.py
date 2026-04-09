"""Drift report storage protocol and SQLite implementation."""

import json
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from synthorg.observability import get_logger
from synthorg.ontology.models import AgentDrift, DriftAction, DriftReport

if TYPE_CHECKING:
    import aiosqlite

    from synthorg.core.types import NotBlankStr

logger = get_logger(__name__)


@runtime_checkable
class DriftReportStore(Protocol):
    """Storage protocol for drift detection reports."""

    async def store_report(self, report: DriftReport) -> None:
        """Persist a drift report.

        Args:
            report: The drift report to store.
        """
        ...

    async def get_latest(
        self,
        entity_name: NotBlankStr,
        *,
        limit: int = 10,
    ) -> tuple[DriftReport, ...]:
        """Get most recent drift reports for an entity.

        Args:
            entity_name: Entity to query.
            limit: Maximum reports to return.

        Returns:
            Reports ordered by most recent first.
        """
        ...

    async def get_all_latest(
        self,
        *,
        limit: int = 100,
    ) -> tuple[DriftReport, ...]:
        """Get the most recent drift report for each entity.

        Args:
            limit: Maximum entities to return.

        Returns:
            Latest report per entity.
        """
        ...


_CREATE_TABLE = """\
CREATE TABLE IF NOT EXISTS drift_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_name TEXT NOT NULL,
    divergence_score REAL NOT NULL,
    canonical_version INTEGER NOT NULL,
    recommendation TEXT NOT NULL,
    divergent_agents TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
)"""

_CREATE_INDEX = """\
CREATE INDEX IF NOT EXISTS idx_dr_entity_created
ON drift_reports(entity_name, created_at DESC)"""


class SQLiteDriftReportStore:
    """SQLite-backed drift report store.

    Args:
        db: aiosqlite database connection.
    """

    __slots__ = ("_db",)

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def apply_schema(self) -> None:
        """Create the drift_reports table if not present."""
        await self._db.execute(_CREATE_TABLE)
        await self._db.execute(_CREATE_INDEX)
        await self._db.commit()

    async def store_report(self, report: DriftReport) -> None:
        """Persist a drift report.

        Args:
            report: The drift report to store.
        """
        agents_json = json.dumps(
            [
                {
                    "agent_id": a.agent_id,
                    "divergence_score": a.divergence_score,
                    "details": a.details,
                }
                for a in report.divergent_agents
            ],
        )
        try:
            await self._db.execute(
                "INSERT INTO drift_reports "
                "(entity_name, divergence_score, canonical_version, "
                "recommendation, divergent_agents) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    report.entity_name,
                    report.divergence_score,
                    report.canonical_version,
                    report.recommendation.value,
                    agents_json,
                ),
            )
            await self._db.commit()
        except Exception:
            logger.error(
                "ontology.drift.store_write_failed",
                entity_name=report.entity_name,
                exc_info=True,
            )
            raise

    async def get_latest(
        self,
        entity_name: NotBlankStr,
        *,
        limit: int = 10,
    ) -> tuple[DriftReport, ...]:
        """Get most recent drift reports for an entity.

        Args:
            entity_name: Entity to query.
            limit: Maximum reports to return.

        Returns:
            Reports ordered by most recent first.
        """
        cursor = await self._db.execute(
            "SELECT entity_name, divergence_score, canonical_version, "
            "recommendation, divergent_agents "
            "FROM drift_reports "
            "WHERE entity_name = ? "
            "ORDER BY id DESC LIMIT ?",
            (entity_name, limit),
        )
        rows = await cursor.fetchall()
        return tuple(_row_to_report(row) for row in rows)

    async def get_all_latest(
        self,
        *,
        limit: int = 100,
    ) -> tuple[DriftReport, ...]:
        """Get the most recent drift report for each entity.

        Args:
            limit: Maximum entities to return.

        Returns:
            Latest report per entity.
        """
        cursor = await self._db.execute(
            "SELECT entity_name, divergence_score, canonical_version, "
            "recommendation, divergent_agents "
            "FROM drift_reports dr "
            "WHERE id = ("
            "  SELECT MAX(id) FROM drift_reports "
            "  WHERE entity_name = dr.entity_name"
            ") "
            "ORDER BY divergence_score DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return tuple(_row_to_report(row) for row in rows)


def _row_to_report(row: Any) -> DriftReport:
    """Deserialise a database row into a DriftReport.

    Args:
        row: (entity_name, divergence_score, canonical_version,
              recommendation, divergent_agents_json).

    Returns:
        Reconstructed DriftReport.

    Raises:
        ValueError: If the row contains malformed data.
    """
    entity_name, divergence_score, canonical_version, rec, agents_json = row
    try:
        agents_data = json.loads(str(agents_json))
        agents = tuple(
            AgentDrift(
                agent_id=a["agent_id"],
                divergence_score=a["divergence_score"],
                details=a.get("details", ""),
            )
            for a in agents_data
        )
        return DriftReport(
            entity_name=str(entity_name),
            divergence_score=float(divergence_score),
            canonical_version=int(canonical_version),
            recommendation=DriftAction(str(rec)),
            divergent_agents=agents,
        )
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        logger.exception(
            "ontology.drift.store_deserialize_failed",
            entity_name=str(entity_name),
        )
        msg = f"Malformed drift report row for entity {entity_name!r}"
        raise ValueError(msg) from exc
