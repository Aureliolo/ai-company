"""Shared fixtures for workflow type tests."""

import pytest

from synthorg.engine.workflow.kanban_board import KanbanConfig, KanbanWipLimit
from synthorg.engine.workflow.kanban_columns import KanbanColumn


@pytest.fixture
def default_kanban_config() -> KanbanConfig:
    """KanbanConfig with default WIP limits."""
    return KanbanConfig()


@pytest.fixture
def strict_kanban_config() -> KanbanConfig:
    """KanbanConfig with tight WIP limits for testing."""
    return KanbanConfig(
        wip_limits=(
            KanbanWipLimit(column=KanbanColumn.IN_PROGRESS, limit=2),
            KanbanWipLimit(column=KanbanColumn.REVIEW, limit=1),
        ),
        enforce_wip=True,
    )


@pytest.fixture
def advisory_kanban_config() -> KanbanConfig:
    """KanbanConfig with advisory (non-enforcing) WIP limits."""
    return KanbanConfig(
        wip_limits=(
            KanbanWipLimit(column=KanbanColumn.IN_PROGRESS, limit=2),
            KanbanWipLimit(column=KanbanColumn.REVIEW, limit=1),
        ),
        enforce_wip=False,
    )
