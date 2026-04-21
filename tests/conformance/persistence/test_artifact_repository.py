"""Conformance tests for ``ArtifactRepository`` (SQLite + Postgres)."""

from datetime import UTC, datetime

import pytest

from synthorg.core.artifact import Artifact
from synthorg.core.enums import ArtifactType
from synthorg.core.types import NotBlankStr
from synthorg.persistence.protocol import PersistenceBackend

pytestmark = pytest.mark.integration


def _artifact(
    *,
    artifact_id: str = "artifact-001",
    artifact_type: ArtifactType = ArtifactType.CODE,
    task_id: str = "task-123",
    created_by: str = "agent-1",
    path: str = "src/auth/login.py",
) -> Artifact:
    return Artifact(
        id=NotBlankStr(artifact_id),
        type=artifact_type,
        path=NotBlankStr(path),
        task_id=NotBlankStr(task_id),
        created_by=NotBlankStr(created_by),
        description="Login endpoint",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


class TestArtifactRepository:
    async def test_save_and_get(self, backend: PersistenceBackend) -> None:
        await backend.artifacts.save(_artifact())

        fetched = await backend.artifacts.get(NotBlankStr("artifact-001"))
        assert fetched is not None
        assert fetched.id == "artifact-001"
        assert fetched.type is ArtifactType.CODE
        assert fetched.task_id == "task-123"

    async def test_get_missing_returns_none(self, backend: PersistenceBackend) -> None:
        assert await backend.artifacts.get(NotBlankStr("ghost")) is None

    async def test_save_upsert(self, backend: PersistenceBackend) -> None:
        a = _artifact()
        await backend.artifacts.save(a)

        updated = a.model_copy(update={"description": "refined"})
        await backend.artifacts.save(updated)

        fetched = await backend.artifacts.get(NotBlankStr("artifact-001"))
        assert fetched is not None
        assert fetched.description == "refined"

    async def test_list_all(self, backend: PersistenceBackend) -> None:
        await backend.artifacts.save(_artifact(artifact_id="a1"))
        await backend.artifacts.save(_artifact(artifact_id="a2"))

        rows = await backend.artifacts.list_artifacts()
        ids = {r.id for r in rows}
        assert {"a1", "a2"} <= ids

    async def test_list_filter_by_task_id(self, backend: PersistenceBackend) -> None:
        await backend.artifacts.save(_artifact(artifact_id="x", task_id="t1"))
        await backend.artifacts.save(_artifact(artifact_id="y", task_id="t2"))

        rows = await backend.artifacts.list_artifacts(task_id=NotBlankStr("t1"))
        assert [r.id for r in rows] == ["x"]

    async def test_list_filter_by_type(self, backend: PersistenceBackend) -> None:
        await backend.artifacts.save(
            _artifact(artifact_id="code", artifact_type=ArtifactType.CODE),
        )
        await backend.artifacts.save(
            _artifact(artifact_id="doc", artifact_type=ArtifactType.DOCUMENTATION),
        )

        rows = await backend.artifacts.list_artifacts(
            artifact_type=ArtifactType.DOCUMENTATION,
        )
        assert [r.id for r in rows] == ["doc"]

    async def test_delete_existing(self, backend: PersistenceBackend) -> None:
        await backend.artifacts.save(_artifact())

        deleted = await backend.artifacts.delete(NotBlankStr("artifact-001"))
        assert deleted is True
        assert await backend.artifacts.get(NotBlankStr("artifact-001")) is None

    async def test_delete_missing(self, backend: PersistenceBackend) -> None:
        assert await backend.artifacts.delete(NotBlankStr("ghost")) is False
