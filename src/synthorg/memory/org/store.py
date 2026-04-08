"""Org fact store protocol -- MVCC persistence contract."""

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


# ── Protocol ────────────────────────────────────────────────────


@runtime_checkable
class OrgFactStore(Protocol):
    """Protocol for organizational fact persistence with MVCC."""

    async def connect(self) -> None:
        """Establish connection to the store."""
        ...

    async def disconnect(self) -> None:
        """Close the store connection."""
        ...

    @property
    def is_connected(self) -> bool:
        """Whether the store has an active connection."""
        ...

    async def save(self, fact: OrgFact) -> None:
        """Publish an organizational fact.

        Appends a PUBLISH entry to the operation log and updates
        the materialized snapshot.  Re-publishing a fact with the
        same ``fact_id`` creates a new version.

        Args:
            fact: The fact to persist.

        Raises:
            OrgMemoryConnectionError: If not connected.
            OrgMemoryWriteError: If the save fails.
        """
        ...

    async def get(self, fact_id: NotBlankStr) -> OrgFact | None:
        """Get an active fact by ID.

        Args:
            fact_id: The fact identifier.

        Returns:
            The fact, or ``None`` if not found or retracted.

        Raises:
            OrgMemoryConnectionError: If not connected.
            OrgMemoryQueryError: If the query fails.
        """
        ...

    async def query(
        self,
        *,
        categories: frozenset[OrgFactCategory] | None = None,
        text: str | None = None,
        limit: int = 5,
    ) -> tuple[OrgFact, ...]:
        """Query active facts by category and/or text.

        Args:
            categories: Category filter.
            text: Text substring filter.
            limit: Maximum results.

        Returns:
            Matching active facts.

        Raises:
            OrgMemoryConnectionError: If not connected.
            OrgMemoryQueryError: If the query fails.
        """
        ...

    async def list_by_category(
        self,
        category: OrgFactCategory,
    ) -> tuple[OrgFact, ...]:
        """List all active facts in a category.

        Args:
            category: The category to list.

        Returns:
            Active facts in the category.

        Raises:
            OrgMemoryConnectionError: If not connected.
            OrgMemoryQueryError: If the query fails.
        """
        ...

    async def delete(
        self,
        fact_id: NotBlankStr,
        *,
        author: OrgFactAuthor,
    ) -> bool:
        """Retract a fact by ID.

        Appends a RETRACT entry to the operation log and marks the
        snapshot as retracted.  The provided ``author`` is recorded
        as the actor who performed the retraction.

        Args:
            fact_id: Fact identifier.
            author: The author performing the retraction.

        Returns:
            ``True`` if retracted, ``False`` if not found or
            already retracted.

        Raises:
            OrgMemoryConnectionError: If not connected.
            OrgMemoryWriteError: If the retraction fails.
        """
        ...

    async def snapshot_at(
        self,
        timestamp: datetime,
    ) -> tuple[OperationLogSnapshot, ...]:
        """Point-in-time snapshot of facts at a given timestamp.

        Reconstructs the state of all facts from the operation log
        up to and including the given timestamp.

        Args:
            timestamp: UTC timestamp for the snapshot.

        Returns:
            Facts as they existed at the given time.  Active facts
            have ``retracted_at=None``.

        Raises:
            OrgMemoryConnectionError: If not connected.
            OrgMemoryQueryError: If the query fails.
        """
        ...

    async def get_operation_log(
        self,
        fact_id: NotBlankStr,
    ) -> tuple[OperationLogEntry, ...]:
        """Retrieve full audit trail for a fact.

        Args:
            fact_id: Fact identifier.

        Returns:
            All operations in chronological (version) order.

        Raises:
            OrgMemoryConnectionError: If not connected.
            OrgMemoryQueryError: If the query fails.
        """
        ...
