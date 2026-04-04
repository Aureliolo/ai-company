"""Tests for SQLite workflow version repository."""

from datetime import UTC, datetime

import aiosqlite
import pytest

from synthorg.core.enums import WorkflowNodeType, WorkflowType
from synthorg.engine.workflow.definition import WorkflowEdge, WorkflowNode
from synthorg.engine.workflow.version import WorkflowDefinitionVersion
from synthorg.persistence.sqlite.workflow_version_repo import (
    SQLiteWorkflowVersionRepository,
)

_NOW = datetime(2026, 4, 1, 12, 0, tzinfo=UTC)
_LATER = datetime(2026, 4, 1, 13, 0, tzinfo=UTC)

_START = WorkflowNode(id="start", type=WorkflowNodeType.START, label="Start")
_END = WorkflowNode(id="end", type=WorkflowNodeType.END, label="End")
_EDGE = WorkflowEdge(id="e1", source_node_id="start", target_node_id="end")

# Must seed a parent definition for FK constraint.
_SEED_SQL = """
INSERT INTO workflow_definitions
    (id, name, description, workflow_type, nodes, edges,
     created_by, created_at, updated_at, version)
VALUES
    ('wfdef-test', 'Test', '', 'sequential_pipeline', '[]', '[]',
     'user', '2026-04-01T12:00:00+00:00', '2026-04-01T12:00:00+00:00', 1)
"""


def _make_version(
    version: int = 1,
    **overrides: object,
) -> WorkflowDefinitionVersion:
    defaults: dict[str, object] = {
        "definition_id": "wfdef-test",
        "version": version,
        "name": "Test Workflow",
        "description": "A test",
        "workflow_type": WorkflowType.SEQUENTIAL_PIPELINE,
        "nodes": (_START, _END),
        "edges": (_EDGE,),
        "created_by": "user",
        "saved_by": "user",
        "saved_at": _NOW,
    }
    defaults.update(overrides)
    return WorkflowDefinitionVersion.model_validate(defaults)


@pytest.fixture
async def repo(
    migrated_db: aiosqlite.Connection,
) -> SQLiteWorkflowVersionRepository:
    """Version repository with parent definition seeded."""
    await migrated_db.execute(_SEED_SQL)
    await migrated_db.commit()
    return SQLiteWorkflowVersionRepository(migrated_db)


class TestSaveAndGetVersion:
    """save_version + get_version roundtrip."""

    @pytest.mark.unit
    async def test_roundtrip(self, repo: SQLiteWorkflowVersionRepository) -> None:
        v = _make_version(1)
        await repo.save_version(v)
        result = await repo.get_version("wfdef-test", 1)
        assert result is not None
        assert result.version == 1
        assert result.name == "Test Workflow"
        assert len(result.nodes) == 2
        assert len(result.edges) == 1

    @pytest.mark.unit
    async def test_get_not_found(self, repo: SQLiteWorkflowVersionRepository) -> None:
        result = await repo.get_version("wfdef-test", 99)
        assert result is None

    @pytest.mark.unit
    async def test_idempotent_save(self, repo: SQLiteWorkflowVersionRepository) -> None:
        """Saving the same version twice does not error."""
        v = _make_version(1)
        await repo.save_version(v)
        await repo.save_version(v)  # Should not raise
        result = await repo.get_version("wfdef-test", 1)
        assert result is not None

    @pytest.mark.unit
    async def test_timestamps_preserved_utc(
        self, repo: SQLiteWorkflowVersionRepository
    ) -> None:
        v = _make_version(1, saved_at=_NOW)
        await repo.save_version(v)
        result = await repo.get_version("wfdef-test", 1)
        assert result is not None
        assert result.saved_at == _NOW
        assert result.saved_at.tzinfo is not None


class TestListVersions:
    """list_versions behavior."""

    @pytest.mark.unit
    async def test_empty_list(self, repo: SQLiteWorkflowVersionRepository) -> None:
        result = await repo.list_versions("wfdef-test")
        assert result == ()

    @pytest.mark.unit
    async def test_ordered_by_version_desc(
        self, repo: SQLiteWorkflowVersionRepository
    ) -> None:
        await repo.save_version(_make_version(1))
        await repo.save_version(_make_version(2, saved_at=_LATER))
        await repo.save_version(_make_version(3, saved_at=_LATER))

        result = await repo.list_versions("wfdef-test")
        versions = [v.version for v in result]
        assert versions == [3, 2, 1]

    @pytest.mark.unit
    async def test_pagination(self, repo: SQLiteWorkflowVersionRepository) -> None:
        for i in range(1, 6):
            await repo.save_version(_make_version(i))

        page1 = await repo.list_versions("wfdef-test", limit=2, offset=0)
        page2 = await repo.list_versions("wfdef-test", limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2
        assert page1[0].version == 5
        assert page2[0].version == 3


class TestCountVersions:
    """count_versions behavior."""

    @pytest.mark.unit
    async def test_count_empty(self, repo: SQLiteWorkflowVersionRepository) -> None:
        assert await repo.count_versions("wfdef-test") == 0

    @pytest.mark.unit
    async def test_count_multiple(self, repo: SQLiteWorkflowVersionRepository) -> None:
        await repo.save_version(_make_version(1))
        await repo.save_version(_make_version(2))
        assert await repo.count_versions("wfdef-test") == 2


class TestDeleteVersions:
    """delete_versions_for_definition behavior."""

    @pytest.mark.unit
    async def test_delete_all(self, repo: SQLiteWorkflowVersionRepository) -> None:
        await repo.save_version(_make_version(1))
        await repo.save_version(_make_version(2))
        count = await repo.delete_versions_for_definition("wfdef-test")
        assert count == 2
        assert await repo.count_versions("wfdef-test") == 0

    @pytest.mark.unit
    async def test_delete_nonexistent(
        self, repo: SQLiteWorkflowVersionRepository
    ) -> None:
        count = await repo.delete_versions_for_definition("wfdef-test")
        assert count == 0
