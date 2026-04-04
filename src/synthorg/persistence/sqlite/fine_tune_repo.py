"""SQLite repositories for fine-tuning pipeline runs and checkpoints."""

import json
import sqlite3
from datetime import UTC, datetime

import aiosqlite

from synthorg.memory.embedding.fine_tune import FineTuneStage
from synthorg.memory.embedding.fine_tune_models import (
    CheckpointRecord,
    EvalMetrics,
    FineTuneRun,
    FineTuneRunConfig,
)
from synthorg.observability import get_logger
from synthorg.observability.events.memory import (
    MEMORY_FINE_TUNE_INTERRUPTED,
    MEMORY_FINE_TUNE_PERSIST_FAILED,
)
from synthorg.persistence.errors import QueryError

logger = get_logger(__name__)

_ACTIVE_STAGES = (
    FineTuneStage.GENERATING_DATA.value,
    FineTuneStage.MINING_NEGATIVES.value,
    FineTuneStage.TRAINING.value,
    FineTuneStage.EVALUATING.value,
    FineTuneStage.DEPLOYING.value,
)


def _run_from_row(row: aiosqlite.Row) -> FineTuneRun:
    """Build a ``FineTuneRun`` from a database row."""
    config = FineTuneRunConfig.model_validate_json(row["config_json"])
    stages = tuple(json.loads(row["stages_completed"]))
    return FineTuneRun(
        id=row["id"],
        stage=FineTuneStage(row["stage"]),
        progress=row["progress"],
        error=row["error"],
        config=config,
        started_at=row["started_at"],
        updated_at=row["updated_at"],
        completed_at=row["completed_at"],
        stages_completed=stages,
    )


def _checkpoint_from_row(row: aiosqlite.Row) -> CheckpointRecord:
    """Build a ``CheckpointRecord`` from a database row."""
    eval_metrics = None
    if row["eval_metrics_json"]:
        eval_metrics = EvalMetrics.model_validate_json(
            row["eval_metrics_json"],
        )
    return CheckpointRecord(
        id=row["id"],
        run_id=row["run_id"],
        model_path=row["model_path"],
        base_model=row["base_model"],
        doc_count=row["doc_count"],
        eval_metrics=eval_metrics,
        size_bytes=row["size_bytes"],
        created_at=row["created_at"],
        is_active=bool(row["is_active"]),
        backup_config_json=row["backup_config_json"],
    )


class SQLiteFineTuneRunRepository:
    """SQLite-backed fine-tuning run repository.

    Args:
        db: An open aiosqlite connection with row_factory set.
    """

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def save_run(self, run: FineTuneRun) -> None:
        """Persist a run (upsert semantics)."""
        try:
            await self._db.execute(
                "INSERT OR REPLACE INTO fine_tune_runs "
                "(id, stage, progress, error, config_json, "
                "started_at, updated_at, completed_at, "
                "stages_completed) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run.id,
                    run.stage.value,
                    run.progress,
                    run.error,
                    run.config.model_dump_json(),
                    run.started_at.isoformat(),
                    run.updated_at.isoformat(),
                    run.completed_at.isoformat() if run.completed_at else None,
                    json.dumps(list(run.stages_completed)),
                ),
            )
            await self._db.commit()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to save fine-tune run {run.id}"
            logger.exception(
                MEMORY_FINE_TUNE_PERSIST_FAILED,
                run_id=run.id,
                error=str(exc),
            )
            raise QueryError(msg) from exc

    async def get_run(self, run_id: str) -> FineTuneRun | None:
        """Retrieve a run by ID."""
        try:
            cursor = await self._db.execute(
                "SELECT * FROM fine_tune_runs WHERE id = ?",
                (run_id,),
            )
            row = await cursor.fetchone()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to get fine-tune run {run_id}"
            raise QueryError(msg) from exc
        if row is None:
            return None
        return _run_from_row(row)

    async def get_active_run(self) -> FineTuneRun | None:
        """Get the currently active run (if any)."""
        placeholders = ", ".join("?" for _ in _ACTIVE_STAGES)
        query = (
            f"SELECT * FROM fine_tune_runs "  # noqa: S608
            f"WHERE stage IN ({placeholders}) "
            "ORDER BY started_at DESC LIMIT 1"
        )
        try:
            cursor = await self._db.execute(query, _ACTIVE_STAGES)
            row = await cursor.fetchone()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = "Failed to query active fine-tune run"
            raise QueryError(msg) from exc
        if row is None:
            return None
        return _run_from_row(row)

    async def list_runs(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[tuple[FineTuneRun, ...], int]:
        """List runs ordered by start time descending.

        Returns:
            Tuple of (runs, total_count).
        """
        try:
            count_cursor = await self._db.execute(
                "SELECT COUNT(*) FROM fine_tune_runs",
            )
            count_row = await count_cursor.fetchone()
            total = count_row[0] if count_row else 0

            cursor = await self._db.execute(
                "SELECT * FROM fine_tune_runs "
                "ORDER BY started_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
            rows = await cursor.fetchall()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = "Failed to list fine-tune runs"
            raise QueryError(msg) from exc
        return tuple(_run_from_row(r) for r in rows), total

    async def update_run(self, run: FineTuneRun) -> None:
        """Update all mutable fields for a run."""
        try:
            await self._db.execute(
                "UPDATE fine_tune_runs SET "
                "stage = ?, progress = ?, error = ?, "
                "updated_at = ?, completed_at = ?, "
                "stages_completed = ? "
                "WHERE id = ?",
                (
                    run.stage.value,
                    run.progress,
                    run.error,
                    run.updated_at.isoformat(),
                    run.completed_at.isoformat() if run.completed_at else None,
                    json.dumps(list(run.stages_completed)),
                    run.id,
                ),
            )
            await self._db.commit()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to update fine-tune run {run.id}"
            raise QueryError(msg) from exc

    async def mark_interrupted(self) -> int:
        """Mark all active runs as FAILED on startup recovery.

        Returns:
            Number of runs marked as interrupted.
        """
        placeholders = ", ".join("?" for _ in _ACTIVE_STAGES)
        now = datetime.now(UTC).isoformat()
        query = (
            f"UPDATE fine_tune_runs SET "  # noqa: S608
            f"stage = ?, error = ?, updated_at = ?, completed_at = ? "
            f"WHERE stage IN ({placeholders})"
        )
        try:
            cursor = await self._db.execute(
                query,
                (
                    FineTuneStage.FAILED.value,
                    "interrupted by restart",
                    now,
                    now,
                    *_ACTIVE_STAGES,
                ),
            )
            await self._db.commit()
            count = cursor.rowcount
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = "Failed to mark interrupted fine-tune runs"
            raise QueryError(msg) from exc
        if count > 0:
            logger.warning(
                MEMORY_FINE_TUNE_INTERRUPTED,
                interrupted_count=count,
            )
        return count


class SQLiteFineTuneCheckpointRepository:
    """SQLite-backed fine-tuning checkpoint repository.

    Args:
        db: An open aiosqlite connection with row_factory set.
    """

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def save_checkpoint(
        self,
        checkpoint: CheckpointRecord,
    ) -> None:
        """Persist a checkpoint (upsert semantics)."""
        try:
            await self._db.execute(
                "INSERT OR REPLACE INTO fine_tune_checkpoints "
                "(id, run_id, model_path, base_model, doc_count, "
                "eval_metrics_json, size_bytes, created_at, "
                "is_active, backup_config_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    checkpoint.id,
                    checkpoint.run_id,
                    checkpoint.model_path,
                    checkpoint.base_model,
                    checkpoint.doc_count,
                    checkpoint.eval_metrics.model_dump_json()
                    if checkpoint.eval_metrics
                    else None,
                    checkpoint.size_bytes,
                    checkpoint.created_at.isoformat(),
                    int(checkpoint.is_active),
                    checkpoint.backup_config_json,
                ),
            )
            await self._db.commit()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to save checkpoint {checkpoint.id}"
            raise QueryError(msg) from exc

    async def get_checkpoint(
        self,
        checkpoint_id: str,
    ) -> CheckpointRecord | None:
        """Retrieve a checkpoint by ID."""
        try:
            cursor = await self._db.execute(
                "SELECT * FROM fine_tune_checkpoints WHERE id = ?",
                (checkpoint_id,),
            )
            row = await cursor.fetchone()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to get checkpoint {checkpoint_id}"
            raise QueryError(msg) from exc
        if row is None:
            return None
        return _checkpoint_from_row(row)

    async def list_checkpoints(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[tuple[CheckpointRecord, ...], int]:
        """List checkpoints ordered by creation time descending.

        Returns:
            Tuple of (checkpoints, total_count).
        """
        try:
            count_cursor = await self._db.execute(
                "SELECT COUNT(*) FROM fine_tune_checkpoints",
            )
            count_row = await count_cursor.fetchone()
            total = count_row[0] if count_row else 0

            cursor = await self._db.execute(
                "SELECT * FROM fine_tune_checkpoints "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
            rows = await cursor.fetchall()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = "Failed to list checkpoints"
            raise QueryError(msg) from exc
        return tuple(_checkpoint_from_row(r) for r in rows), total

    async def set_active(self, checkpoint_id: str) -> None:
        """Deactivate all checkpoints and activate the given one.

        Uses a single transaction to ensure atomicity.

        Raises:
            QueryError: If the checkpoint does not exist or DB fails.
        """
        try:
            await self._db.execute("BEGIN IMMEDIATE")
            await self._db.execute(
                "UPDATE fine_tune_checkpoints SET is_active = 0",
            )
            cursor = await self._db.execute(
                "UPDATE fine_tune_checkpoints SET is_active = 1 WHERE id = ?",
                (checkpoint_id,),
            )
            affected = cursor.rowcount
            await self._db.execute("COMMIT")
        except (sqlite3.Error, aiosqlite.Error) as exc:
            await self._db.execute("ROLLBACK")
            msg = f"Failed to activate checkpoint {checkpoint_id}"
            raise QueryError(msg) from exc
        if affected == 0:
            msg = f"Checkpoint {checkpoint_id} not found"
            raise QueryError(msg)

    async def deactivate_all(self) -> None:
        """Deactivate all checkpoints (for rollback)."""
        try:
            await self._db.execute(
                "UPDATE fine_tune_checkpoints SET is_active = 0",
            )
            await self._db.commit()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = "Failed to deactivate all checkpoints"
            raise QueryError(msg) from exc

    async def delete_checkpoint(
        self,
        checkpoint_id: str,
    ) -> None:
        """Delete a checkpoint atomically. Raises if it is the active one.

        Uses a conditional DELETE to avoid TOCTOU races.
        """
        is_active = False
        try:
            cursor = await self._db.execute(
                "DELETE FROM fine_tune_checkpoints WHERE id = ? AND is_active = 0",
                (checkpoint_id,),
            )
            await self._db.commit()
            if cursor.rowcount == 0:
                # Check if it exists but is active.
                check = await self._db.execute(
                    "SELECT is_active FROM fine_tune_checkpoints WHERE id = ?",
                    (checkpoint_id,),
                )
                row = await check.fetchone()
                is_active = row is not None and bool(row["is_active"])
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = f"Failed to delete checkpoint {checkpoint_id}"
            raise QueryError(msg) from exc
        if is_active:
            msg = f"Cannot delete active checkpoint {checkpoint_id}"
            raise QueryError(msg)

    async def get_active_checkpoint(
        self,
    ) -> CheckpointRecord | None:
        """Get the currently active checkpoint (if any)."""
        try:
            cursor = await self._db.execute(
                "SELECT * FROM fine_tune_checkpoints WHERE is_active = 1 LIMIT 1",
            )
            row = await cursor.fetchone()
        except (sqlite3.Error, aiosqlite.Error) as exc:
            msg = "Failed to query active checkpoint"
            raise QueryError(msg) from exc
        if row is None:
            return None
        return _checkpoint_from_row(row)
