"""Tests for MemoryConsolidationService."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
import structlog.testing

from synthorg.core.enums import MemoryCategory
from synthorg.memory.consolidation.config import (
    ArchivalConfig,
    ConsolidationConfig,
    RetentionConfig,
)
from synthorg.memory.consolidation.models import (
    ArchivalMode,
    ArchivalModeAssignment,
    ConsolidationResult,
)
from synthorg.memory.consolidation.service import MemoryConsolidationService
from synthorg.memory.models import MemoryEntry, MemoryMetadata

_NOW = datetime.now(UTC)
_AGENT_ID = "test-agent"


def _make_entry(entry_id: str) -> MemoryEntry:
    return MemoryEntry(
        id=entry_id,
        agent_id=_AGENT_ID,
        category=MemoryCategory.EPISODIC,
        content=f"Content {entry_id}",
        metadata=MemoryMetadata(),
        created_at=_NOW - timedelta(hours=1),
    )


def _make_backend_mock(
    entries: tuple[MemoryEntry, ...] = (),
    count: int = 0,
) -> AsyncMock:
    backend = AsyncMock()
    backend.retrieve = AsyncMock(return_value=entries)
    backend.delete = AsyncMock(return_value=True)
    backend.count = AsyncMock(return_value=count)
    return backend


@pytest.mark.unit
class TestRunConsolidation:
    """run_consolidation behaviour."""

    async def test_no_strategy_returns_empty(self) -> None:
        backend = _make_backend_mock()
        config = ConsolidationConfig()
        service = MemoryConsolidationService(
            backend=backend,
            config=config,
            strategy=None,
        )
        result = await service.run_consolidation(_AGENT_ID)
        assert result.consolidated_count == 0

    async def test_run_consolidation_skipped_when_no_strategy(self) -> None:
        backend = _make_backend_mock()
        config = ConsolidationConfig()
        service = MemoryConsolidationService(
            backend=backend,
            config=config,
            strategy=None,
        )
        with structlog.testing.capture_logs() as logs:
            result = await service.run_consolidation(_AGENT_ID)
        assert result.consolidated_count == 0
        assert result.removed_ids == ()
        assert result.summary_id is None
        assert any(log.get("event") == "consolidation.run.skipped" for log in logs)

    async def test_with_strategy(self) -> None:
        entries = (_make_entry("m1"), _make_entry("m2"))
        backend = _make_backend_mock(entries=entries)

        strategy = AsyncMock()
        strategy.consolidate = AsyncMock(
            return_value=ConsolidationResult(
                removed_ids=("m1",),
                summary_id="summary-1",
            ),
        )

        config = ConsolidationConfig()
        service = MemoryConsolidationService(
            backend=backend,
            config=config,
            strategy=strategy,
        )
        result = await service.run_consolidation(_AGENT_ID)
        assert result.consolidated_count == 1
        assert result.summary_id == "summary-1"

    async def test_run_consolidation_exception_propagates(self) -> None:
        entries = (_make_entry("m1"),)
        backend = _make_backend_mock(entries=entries)

        strategy = AsyncMock()
        strategy.consolidate = AsyncMock(
            side_effect=RuntimeError("strategy failure"),
        )

        config = ConsolidationConfig()
        service = MemoryConsolidationService(
            backend=backend,
            config=config,
            strategy=strategy,
        )
        with pytest.raises(RuntimeError, match="strategy failure"):
            await service.run_consolidation(_AGENT_ID)

    async def test_with_archival(self) -> None:
        entries = (_make_entry("m1"), _make_entry("m2"))
        backend = _make_backend_mock(entries=entries)

        strategy = AsyncMock()
        strategy.consolidate = AsyncMock(
            return_value=ConsolidationResult(
                removed_ids=("m1",),
            ),
        )

        archival = AsyncMock()
        archival.archive = AsyncMock(return_value="arch-1")

        config = ConsolidationConfig(
            archival=ArchivalConfig(enabled=True),
        )
        service = MemoryConsolidationService(
            backend=backend,
            config=config,
            strategy=strategy,
            archival_store=archival,
        )
        result = await service.run_consolidation(_AGENT_ID)
        assert result.archived_count == 1
        archival.archive.assert_called_once()


@pytest.mark.unit
class TestEnforceMaxMemories:
    """enforce_max_memories behaviour."""

    async def test_under_limit(self) -> None:
        backend = _make_backend_mock(count=5)
        config = ConsolidationConfig(max_memories_per_agent=100)
        service = MemoryConsolidationService(
            backend=backend,
            config=config,
        )
        deleted = await service.enforce_max_memories(_AGENT_ID)
        assert deleted == 0

    async def test_over_limit_deletes_excess(self) -> None:
        entries = tuple(_make_entry(f"m{i}") for i in range(3))
        backend = _make_backend_mock(entries=entries, count=13)
        config = ConsolidationConfig(max_memories_per_agent=10)
        service = MemoryConsolidationService(
            backend=backend,
            config=config,
        )
        deleted = await service.enforce_max_memories(_AGENT_ID)
        assert deleted == 3

    async def test_enforce_max_memories_delete_returns_false(self) -> None:
        entries = tuple(_make_entry(f"m{i}") for i in range(3))
        backend = _make_backend_mock(entries=entries, count=13)
        backend.delete = AsyncMock(side_effect=[True, False, True])

        config = ConsolidationConfig(max_memories_per_agent=10)
        service = MemoryConsolidationService(
            backend=backend,
            config=config,
        )
        deleted = await service.enforce_max_memories(_AGENT_ID)
        assert deleted == 2


@pytest.mark.unit
class TestCleanupRetention:
    """cleanup_retention delegates to RetentionEnforcer."""

    async def test_delegates_to_retention(self) -> None:
        backend = AsyncMock()
        backend.retrieve = AsyncMock(return_value=())
        config = ConsolidationConfig(
            retention=RetentionConfig(),
        )
        service = MemoryConsolidationService(
            backend=backend,
            config=config,
        )
        deleted = await service.cleanup_retention(_AGENT_ID)
        assert deleted == 0


@pytest.mark.unit
class TestRunMaintenance:
    """run_maintenance orchestrates all steps."""

    async def test_full_maintenance(self) -> None:
        backend = _make_backend_mock(count=5)
        strategy = AsyncMock()
        strategy.consolidate = AsyncMock(
            return_value=ConsolidationResult(),
        )

        config = ConsolidationConfig(max_memories_per_agent=100)
        service = MemoryConsolidationService(
            backend=backend,
            config=config,
            strategy=strategy,
        )
        result = await service.run_maintenance(_AGENT_ID)
        assert result.consolidated_count == 0
        strategy.consolidate.assert_called_once()

    async def test_maintenance_propagates_enforce_error(self) -> None:
        """Item 13: run_maintenance propagates sub-step errors."""
        backend = AsyncMock()
        backend.retrieve = AsyncMock(return_value=())
        backend.count = AsyncMock(side_effect=RuntimeError("backend down"))
        config = ConsolidationConfig(max_memories_per_agent=10)
        service = MemoryConsolidationService(backend=backend, config=config)
        with pytest.raises(RuntimeError, match="backend down"):
            await service.run_maintenance(_AGENT_ID)


@pytest.mark.unit
class TestEnforceMaxMemoriesErrors:
    """enforce_max_memories error propagation (Item 14)."""

    async def test_count_error_propagates(self) -> None:
        backend = AsyncMock()
        backend.count = AsyncMock(side_effect=RuntimeError("count failed"))
        config = ConsolidationConfig(max_memories_per_agent=10)
        service = MemoryConsolidationService(backend=backend, config=config)
        with pytest.raises(RuntimeError, match="count failed"):
            await service.enforce_max_memories(_AGENT_ID)

    async def test_retrieve_error_propagates(self) -> None:
        backend = _make_backend_mock(count=15)
        backend.retrieve = AsyncMock(
            side_effect=RuntimeError("retrieve failed"),
        )
        config = ConsolidationConfig(max_memories_per_agent=10)
        service = MemoryConsolidationService(backend=backend, config=config)
        with pytest.raises(RuntimeError, match="retrieve failed"):
            await service.enforce_max_memories(_AGENT_ID)


@pytest.mark.unit
class TestArchivalResilience:
    """Archival per-entry error resilience (Item 1)."""

    async def test_archival_continues_on_per_entry_failure(self) -> None:
        """A single archival failure does not abort remaining entries."""
        entries = (_make_entry("m1"), _make_entry("m2"), _make_entry("m3"))
        backend = _make_backend_mock(entries=entries)

        strategy = AsyncMock()
        strategy.consolidate = AsyncMock(
            return_value=ConsolidationResult(
                removed_ids=("m1", "m2", "m3"),
            ),
        )

        archival = AsyncMock()
        archival.archive = AsyncMock(
            side_effect=[
                "arch-1",  # m1 succeeds
                RuntimeError("disk full"),  # m2 fails
                "arch-3",  # m3 succeeds
            ],
        )

        config = ConsolidationConfig(
            archival=ArchivalConfig(enabled=True),
        )
        service = MemoryConsolidationService(
            backend=backend,
            config=config,
            strategy=strategy,
            archival_store=archival,
        )
        result = await service.run_consolidation(_AGENT_ID)
        assert result.archived_count == 2
        assert archival.archive.call_count == 3


@pytest.mark.unit
class TestArchivalModeAware:
    """Mode-aware archival with archival index (dual-mode)."""

    async def test_archival_sets_mode_on_entry(self) -> None:
        """ArchivalEntry receives archival_mode from strategy assignments."""
        entries = (_make_entry("m1"), _make_entry("m2"))
        backend = _make_backend_mock(entries=entries)

        strategy = AsyncMock()
        strategy.consolidate = AsyncMock(
            return_value=ConsolidationResult(
                removed_ids=("m1",),
                mode_assignments=(
                    ArchivalModeAssignment(
                        original_id="m1",
                        mode=ArchivalMode.EXTRACTIVE,
                    ),
                ),
            ),
        )

        archival = AsyncMock()
        archival.archive = AsyncMock(return_value="arch-1")

        config = ConsolidationConfig(
            archival=ArchivalConfig(enabled=True),
        )
        service = MemoryConsolidationService(
            backend=backend,
            config=config,
            strategy=strategy,
            archival_store=archival,
        )
        await service.run_consolidation(_AGENT_ID)

        call_args = archival.archive.call_args[0][0]
        assert call_args.archival_mode == ArchivalMode.EXTRACTIVE

    async def test_archival_builds_index(self) -> None:
        """run_consolidation result includes archival_index."""
        entries = (_make_entry("m1"), _make_entry("m2"))
        backend = _make_backend_mock(entries=entries)

        strategy = AsyncMock()
        strategy.consolidate = AsyncMock(
            return_value=ConsolidationResult(
                removed_ids=("m1", "m2"),
                mode_assignments=(
                    ArchivalModeAssignment(
                        original_id="m1",
                        mode=ArchivalMode.ABSTRACTIVE,
                    ),
                    ArchivalModeAssignment(
                        original_id="m2",
                        mode=ArchivalMode.EXTRACTIVE,
                    ),
                ),
            ),
        )

        archival = AsyncMock()
        archival.archive = AsyncMock(
            side_effect=["arch-1", "arch-2"],
        )

        config = ConsolidationConfig(
            archival=ArchivalConfig(enabled=True),
        )
        service = MemoryConsolidationService(
            backend=backend,
            config=config,
            strategy=strategy,
            archival_store=archival,
        )
        result = await service.run_consolidation(_AGENT_ID)

        assert result.archived_count == 2
        assert len(result.archival_index) == 2
        index_map = {e.original_id: e for e in result.archival_index}
        assert index_map["m1"].archival_id == "arch-1"
        assert index_map["m1"].mode == ArchivalMode.ABSTRACTIVE
        assert index_map["m2"].archival_id == "arch-2"
        assert index_map["m2"].mode == ArchivalMode.EXTRACTIVE

    async def test_archival_index_keyed_by_original_id(self) -> None:
        """Archival index maps by original_id, not by position."""
        entries = (_make_entry("m1"), _make_entry("m2"), _make_entry("m3"))
        backend = _make_backend_mock(entries=entries)

        # Mode assignments in REVERSED order from removed_ids
        strategy = AsyncMock()
        strategy.consolidate = AsyncMock(
            return_value=ConsolidationResult(
                removed_ids=("m1", "m2", "m3"),
                mode_assignments=(
                    ArchivalModeAssignment(
                        original_id="m3",
                        mode=ArchivalMode.EXTRACTIVE,
                    ),
                    ArchivalModeAssignment(
                        original_id="m1",
                        mode=ArchivalMode.ABSTRACTIVE,
                    ),
                    ArchivalModeAssignment(
                        original_id="m2",
                        mode=ArchivalMode.EXTRACTIVE,
                    ),
                ),
            ),
        )

        archival = AsyncMock()
        # Second archival fails -- only m1 and m3 succeed
        archival.archive = AsyncMock(
            side_effect=["arch-1", RuntimeError("disk full"), "arch-3"],
        )

        config = ConsolidationConfig(
            archival=ArchivalConfig(enabled=True),
        )
        service = MemoryConsolidationService(
            backend=backend,
            config=config,
            strategy=strategy,
            archival_store=archival,
        )
        result = await service.run_consolidation(_AGENT_ID)

        assert result.archived_count == 2
        assert len(result.archival_index) == 2
        index_map = {e.original_id: e for e in result.archival_index}
        assert index_map["m1"].archival_id == "arch-1"
        assert index_map["m1"].mode == ArchivalMode.ABSTRACTIVE
        assert index_map["m3"].archival_id == "arch-3"
        assert index_map["m3"].mode == ArchivalMode.EXTRACTIVE
        assert "m2" not in index_map

    async def test_archival_no_mode_assignments_uses_extractive(
        self,
    ) -> None:
        """Strategy without mode_assignments defaults to EXTRACTIVE."""
        entries = (_make_entry("m1"),)
        backend = _make_backend_mock(entries=entries)

        strategy = AsyncMock()
        strategy.consolidate = AsyncMock(
            return_value=ConsolidationResult(
                removed_ids=("m1",),
            ),
        )

        archival = AsyncMock()
        archival.archive = AsyncMock(return_value="arch-1")

        config = ConsolidationConfig(
            archival=ArchivalConfig(enabled=True),
        )
        service = MemoryConsolidationService(
            backend=backend,
            config=config,
            strategy=strategy,
            archival_store=archival,
        )
        result = await service.run_consolidation(_AGENT_ID)

        call_args = archival.archive.call_args[0][0]
        assert call_args.archival_mode == ArchivalMode.EXTRACTIVE
        assert len(result.archival_index) == 1
        assert result.archival_index[0].mode == ArchivalMode.EXTRACTIVE
