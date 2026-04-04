"""Tests for fine-tuning pipeline SQLite repositories."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite
import pytest

from synthorg.memory.embedding.fine_tune import FineTuneStage
from synthorg.memory.embedding.fine_tune_models import (
    CheckpointRecord,
    EvalMetrics,
    FineTuneRun,
    FineTuneRunConfig,
)
from synthorg.persistence.errors import QueryError
from synthorg.persistence.sqlite.fine_tune_repo import (
    SQLiteFineTuneCheckpointRepository,
    SQLiteFineTuneRunRepository,
)

_SCHEMA_PATH = Path("src/synthorg/persistence/sqlite/schema.sql")


def _cfg() -> FineTuneRunConfig:
    return FineTuneRunConfig(
        source_dir="/docs",
        base_model="test-model",
        output_dir="/out",
    )


def _run(
    run_id: str = "run-1",
    stage: FineTuneStage = FineTuneStage.GENERATING_DATA,
    **overrides: object,
) -> FineTuneRun:
    now = datetime.now(tz=UTC)
    defaults: dict[str, object] = {
        "id": run_id,
        "stage": stage,
        "config": _cfg(),
        "started_at": now,
        "updated_at": now,
    }
    # Terminal stages need completed_at for validator.
    if stage in {FineTuneStage.COMPLETE, FineTuneStage.FAILED}:
        defaults.setdefault("completed_at", now)
    if stage == FineTuneStage.FAILED:
        defaults.setdefault("error", "test failure")
    defaults.update(overrides)
    return FineTuneRun(**defaults)  # type: ignore[arg-type]


def _checkpoint(
    cp_id: str = "cp-1",
    run_id: str = "run-1",
    **overrides: object,
) -> CheckpointRecord:
    now = datetime.now(tz=UTC)
    defaults: dict[str, object] = {
        "id": cp_id,
        "run_id": run_id,
        "model_path": "/models/cp",
        "base_model": "test-model",
        "doc_count": 100,
        "size_bytes": 4096,
        "created_at": now,
    }
    defaults.update(overrides)
    return CheckpointRecord(**defaults)  # type: ignore[arg-type]


@pytest.fixture
async def db() -> AsyncGenerator[aiosqlite.Connection]:
    """In-memory SQLite with schema applied."""
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON")
    schema = _SCHEMA_PATH.read_text()  # noqa: ASYNC240
    await conn.executescript(schema)
    yield conn
    await conn.close()


@pytest.fixture
def run_repo(db: aiosqlite.Connection) -> SQLiteFineTuneRunRepository:
    return SQLiteFineTuneRunRepository(db)


@pytest.fixture
def cp_repo(
    db: aiosqlite.Connection,
) -> SQLiteFineTuneCheckpointRepository:
    return SQLiteFineTuneCheckpointRepository(db)


# -- Run repository ---------------------------------------------------


@pytest.mark.unit
class TestRunRepository:
    async def test_save_and_get(
        self,
        run_repo: SQLiteFineTuneRunRepository,
    ) -> None:
        run = _run()
        await run_repo.save_run(run)
        fetched = await run_repo.get_run("run-1")
        assert fetched is not None
        assert fetched.id == "run-1"
        assert fetched.stage == FineTuneStage.GENERATING_DATA

    async def test_get_missing_returns_none(
        self,
        run_repo: SQLiteFineTuneRunRepository,
    ) -> None:
        assert await run_repo.get_run("nope") is None

    async def test_get_active_run(
        self,
        run_repo: SQLiteFineTuneRunRepository,
    ) -> None:
        await run_repo.save_run(
            _run("r1", FineTuneStage.TRAINING),
        )
        await run_repo.save_run(
            _run("r2", FineTuneStage.COMPLETE),
        )
        active = await run_repo.get_active_run()
        assert active is not None
        assert active.id == "r1"

    async def test_get_active_run_none(
        self,
        run_repo: SQLiteFineTuneRunRepository,
    ) -> None:
        await run_repo.save_run(
            _run("r1", FineTuneStage.COMPLETE),
        )
        assert await run_repo.get_active_run() is None

    async def test_list_runs(
        self,
        run_repo: SQLiteFineTuneRunRepository,
    ) -> None:
        await run_repo.save_run(_run("r1"))
        await run_repo.save_run(_run("r2"))
        runs, total = await run_repo.list_runs()
        assert total == 2
        assert len(runs) == 2

    async def test_list_runs_pagination(
        self,
        run_repo: SQLiteFineTuneRunRepository,
    ) -> None:
        for i in range(5):
            await run_repo.save_run(_run(f"r{i}"))
        runs, total = await run_repo.list_runs(limit=2, offset=0)
        assert total == 5
        assert len(runs) == 2

    async def test_update_run(
        self,
        run_repo: SQLiteFineTuneRunRepository,
    ) -> None:
        run = _run()
        await run_repo.save_run(run)
        updated = run.model_copy(
            update={
                "stage": FineTuneStage.TRAINING,
                "progress": 0.5,
                "stages_completed": ("generating_data", "mining_negatives"),
            },
        )
        await run_repo.update_run(updated)
        fetched = await run_repo.get_run("run-1")
        assert fetched is not None
        assert fetched.stage == FineTuneStage.TRAINING
        assert fetched.progress == 0.5
        assert fetched.stages_completed == (
            "generating_data",
            "mining_negatives",
        )

    async def test_mark_interrupted(
        self,
        run_repo: SQLiteFineTuneRunRepository,
    ) -> None:
        await run_repo.save_run(
            _run("r1", FineTuneStage.TRAINING),
        )
        await run_repo.save_run(
            _run("r2", FineTuneStage.COMPLETE),
        )
        count = await run_repo.mark_interrupted()
        assert count == 1
        fetched = await run_repo.get_run("r1")
        assert fetched is not None
        assert fetched.stage == FineTuneStage.FAILED
        assert fetched.error == "interrupted by restart"
        # Completed run should be unchanged.
        r2 = await run_repo.get_run("r2")
        assert r2 is not None
        assert r2.stage == FineTuneStage.COMPLETE

    async def test_mark_interrupted_none_active(
        self,
        run_repo: SQLiteFineTuneRunRepository,
    ) -> None:
        assert await run_repo.mark_interrupted() == 0


# -- Checkpoint repository --------------------------------------------


@pytest.mark.unit
class TestCheckpointRepository:
    async def test_save_and_get(
        self,
        run_repo: SQLiteFineTuneRunRepository,
        cp_repo: SQLiteFineTuneCheckpointRepository,
    ) -> None:
        await run_repo.save_run(_run())
        cp = _checkpoint()
        await cp_repo.save_checkpoint(cp)
        fetched = await cp_repo.get_checkpoint("cp-1")
        assert fetched is not None
        assert fetched.id == "cp-1"
        assert fetched.doc_count == 100

    async def test_get_missing_returns_none(
        self,
        cp_repo: SQLiteFineTuneCheckpointRepository,
    ) -> None:
        assert await cp_repo.get_checkpoint("nope") is None

    async def test_list_checkpoints(
        self,
        run_repo: SQLiteFineTuneRunRepository,
        cp_repo: SQLiteFineTuneCheckpointRepository,
    ) -> None:
        await run_repo.save_run(_run())
        await cp_repo.save_checkpoint(_checkpoint("cp-1"))
        await cp_repo.save_checkpoint(_checkpoint("cp-2"))
        cps, total = await cp_repo.list_checkpoints()
        assert total == 2
        assert len(cps) == 2

    async def test_set_active(
        self,
        run_repo: SQLiteFineTuneRunRepository,
        cp_repo: SQLiteFineTuneCheckpointRepository,
    ) -> None:
        await run_repo.save_run(_run())
        await cp_repo.save_checkpoint(_checkpoint("cp-1"))
        await cp_repo.save_checkpoint(_checkpoint("cp-2"))
        await cp_repo.set_active("cp-2")
        active = await cp_repo.get_active_checkpoint()
        assert active is not None
        assert active.id == "cp-2"
        # cp-1 should not be active.
        cp1 = await cp_repo.get_checkpoint("cp-1")
        assert cp1 is not None
        assert cp1.is_active is False

    async def test_delete_checkpoint(
        self,
        run_repo: SQLiteFineTuneRunRepository,
        cp_repo: SQLiteFineTuneCheckpointRepository,
    ) -> None:
        await run_repo.save_run(_run())
        await cp_repo.save_checkpoint(_checkpoint("cp-1"))
        await cp_repo.delete_checkpoint("cp-1")
        assert await cp_repo.get_checkpoint("cp-1") is None

    async def test_delete_active_checkpoint_raises(
        self,
        run_repo: SQLiteFineTuneRunRepository,
        cp_repo: SQLiteFineTuneCheckpointRepository,
    ) -> None:
        await run_repo.save_run(_run())
        await cp_repo.save_checkpoint(_checkpoint("cp-1"))
        await cp_repo.set_active("cp-1")
        with pytest.raises(QueryError, match="active"):
            await cp_repo.delete_checkpoint("cp-1")

    async def test_checkpoint_with_eval_metrics(
        self,
        run_repo: SQLiteFineTuneRunRepository,
        cp_repo: SQLiteFineTuneCheckpointRepository,
    ) -> None:
        await run_repo.save_run(_run())
        metrics = EvalMetrics(
            ndcg_at_10=0.6,
            recall_at_10=0.7,
            base_ndcg_at_10=0.5,
            base_recall_at_10=0.6,
        )
        await cp_repo.save_checkpoint(
            _checkpoint("cp-1", eval_metrics=metrics),
        )
        fetched = await cp_repo.get_checkpoint("cp-1")
        assert fetched is not None
        assert fetched.eval_metrics is not None
        assert fetched.eval_metrics.ndcg_at_10 == 0.6

    async def test_get_active_checkpoint_none(
        self,
        cp_repo: SQLiteFineTuneCheckpointRepository,
    ) -> None:
        assert await cp_repo.get_active_checkpoint() is None
