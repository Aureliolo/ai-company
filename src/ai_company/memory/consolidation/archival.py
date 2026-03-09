"""Archival store protocol for long-term memory storage.

Defines the protocol for moving memories from the hot store into
cold (archival) storage, with search and restore capabilities.
"""

from typing import Protocol, runtime_checkable

from ai_company.core.types import NotBlankStr  # noqa: TC001
from ai_company.memory.consolidation.models import ArchivalEntry  # noqa: TC001
from ai_company.memory.models import MemoryQuery  # noqa: TC001


@runtime_checkable
class ArchivalStore(Protocol):
    """Protocol for long-term memory archival storage.

    Concrete implementations handle moving memories from the hot
    (active) store into cold storage for long-term preservation.
    """

    async def archive(self, entry: ArchivalEntry) -> NotBlankStr:
        """Archive a memory entry.

        Args:
            entry: The archival entry to store.

        Returns:
            The assigned archive entry ID.
        """
        ...

    async def search(self, query: MemoryQuery) -> tuple[ArchivalEntry, ...]:
        """Search archived entries.

        Args:
            query: Search parameters.

        Returns:
            Matching archived entries.
        """
        ...

    async def restore(self, entry_id: NotBlankStr) -> ArchivalEntry | None:
        """Restore a specific archived entry.

        Args:
            entry_id: The archive entry ID.

        Returns:
            The archived entry, or ``None`` if not found.
        """
        ...

    async def count(self, agent_id: NotBlankStr) -> int:
        """Count archived entries for an agent.

        Args:
            agent_id: Agent identifier.

        Returns:
            Number of archived entries.
        """
        ...
