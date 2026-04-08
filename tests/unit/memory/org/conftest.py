"""Shared pytest fixtures and helpers for org memory tests."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest

from synthorg.core.enums import AutonomyLevel, OrgFactCategory, SeniorityLevel
from synthorg.memory.org.models import OrgFact, OrgFactAuthor
from synthorg.memory.org.sqlite_store import SQLiteOrgFactStore

_NOW = datetime.now(UTC)
HUMAN_AUTHOR = OrgFactAuthor(is_human=True)
AGENT_AUTHOR = OrgFactAuthor(
    agent_id="agent-1",
    seniority=SeniorityLevel.SENIOR,
    autonomy_level=AutonomyLevel.SEMI,
    is_human=False,
)


def _make_fact(
    fact_id: str = "fact-1",
    content: str = "Test fact",
    category: OrgFactCategory = OrgFactCategory.ADR,
    *,
    author: OrgFactAuthor = HUMAN_AUTHOR,
    tags: tuple[str, ...] = (),
) -> OrgFact:
    """Create a test OrgFact with sensible defaults."""
    return OrgFact(
        id=fact_id,
        content=content,
        category=category,
        tags=tags,
        author=author,
        created_at=_NOW,
    )


@pytest.fixture
async def connected_store() -> AsyncGenerator[SQLiteOrgFactStore]:
    """Fixture providing a connected SQLiteOrgFactStore with automatic cleanup."""
    store = SQLiteOrgFactStore(":memory:")
    await store.connect()
    yield store
    await store.disconnect()
