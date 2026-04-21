"""Conformance tests for ``CheckpointRepository`` (SQLite + Postgres)."""

import pytest

from synthorg.core.types import NotBlankStr
from synthorg.engine.checkpoint.models import Checkpoint
from synthorg.persistence.protocol import PersistenceBackend

pytestmark = pytest.mark.integration


def _checkpoint(
    *,
    checkpoint_id: str = "cp-001",
    execution_id: str = "exec-001",
    turn_number: int = 1,
) -> Checkpoint:
    return Checkpoint(
        id=NotBlankStr(checkpoint_id),
        execution_id=NotBlankStr(execution_id),
        agent_id=NotBlankStr("agent-001"),
        task_id=NotBlankStr("task-001"),
        turn_number=turn_number,
        context_json='{"state": "running"}',
    )


class TestCheckpointRepository:
    async def test_save_and_get_latest(self, backend: PersistenceBackend) -> None:
        cp = _checkpoint()
        await backend.checkpoints.save(cp)

        result = await backend.checkpoints.get_latest(
            execution_id=NotBlankStr("exec-001"),
        )
        assert result is not None
        assert result.id == "cp-001"
        assert result.turn_number == 1

    async def test_get_latest_missing_returns_none(
        self, backend: PersistenceBackend
    ) -> None:
        result = await backend.checkpoints.get_latest(
            execution_id=NotBlankStr("ghost"),
        )
        assert result is None

    async def test_get_latest_returns_highest_turn(
        self, backend: PersistenceBackend
    ) -> None:
        await backend.checkpoints.save(_checkpoint(checkpoint_id="a", turn_number=1))
        await backend.checkpoints.save(_checkpoint(checkpoint_id="c", turn_number=5))
        await backend.checkpoints.save(_checkpoint(checkpoint_id="b", turn_number=3))

        latest = await backend.checkpoints.get_latest(
            execution_id=NotBlankStr("exec-001"),
        )
        assert latest is not None
        assert latest.turn_number == 5
        assert latest.id == "c"

    async def test_delete_by_execution_removes_all(
        self, backend: PersistenceBackend
    ) -> None:
        await backend.checkpoints.save(_checkpoint(checkpoint_id="a", turn_number=1))
        await backend.checkpoints.save(_checkpoint(checkpoint_id="b", turn_number=2))
        await backend.checkpoints.save(
            _checkpoint(
                checkpoint_id="other",
                execution_id="exec-other",
                turn_number=1,
            ),
        )

        removed = await backend.checkpoints.delete_by_execution(
            NotBlankStr("exec-001"),
        )
        assert removed == 2

        assert (
            await backend.checkpoints.get_latest(execution_id=NotBlankStr("exec-001"))
            is None
        )
        other = await backend.checkpoints.get_latest(
            execution_id=NotBlankStr("exec-other"),
        )
        assert other is not None
