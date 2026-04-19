"""Org-memory repository protocol -- MVCC persistence contract.

Lives in persistence/ so the durable-state contract is colocated
with every other repository protocol.  Domain types stay in
``synthorg.memory.org.models``.
"""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import datetime

    from synthorg.core.enums import OrgFactCategory
    from synthorg.core.types import NotBlankStr
    from synthorg.memory.org.models import (
        OperationLogEntry,
        OperationLogSnapshot,
        OrgFact,
        OrgFactAuthor,
    )


@runtime_checkable
class OrgFactRepository(Protocol):
    """Protocol for organizational fact persistence with MVCC."""

    async def save(self, fact: OrgFact) -> None:
        """Publish an organizational fact."""
        ...

    async def get(self, fact_id: NotBlankStr) -> OrgFact | None:
        """Get an active fact by ID."""
        ...

    async def query(
        self,
        *,
        categories: frozenset[OrgFactCategory] | None = None,
        text: str | None = None,
        limit: int = 5,
    ) -> tuple[OrgFact, ...]:
        """Query active facts by category and/or text substring."""
        ...

    async def list_by_category(
        self,
        category: OrgFactCategory,
    ) -> tuple[OrgFact, ...]:
        """List all active facts in a category."""
        ...

    async def delete(
        self,
        fact_id: NotBlankStr,
        *,
        author: OrgFactAuthor,
    ) -> bool:
        """Retract a fact by ID.  Returns ``True`` if retracted."""
        ...

    async def snapshot_at(
        self,
        timestamp: datetime,
    ) -> tuple[OperationLogSnapshot, ...]:
        """Point-in-time snapshot of facts at the given timestamp."""
        ...

    async def get_operation_log(
        self,
        fact_id: NotBlankStr,
    ) -> tuple[OperationLogEntry, ...]:
        """Retrieve full audit trail for a fact."""
        ...
