"""TTL-based memory pruning strategy.

Removes procedural memory entries that have exceeded a maximum age.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from synthorg.core.types import NotBlankStr
    from synthorg.memory.models import MemoryEntry


class TtlPruningStrategy:
    """Remove entries older than max_age_days.

    Attributes:
        max_age_days: Maximum age in days for entries (default 90).
    """

    def __init__(self, max_age_days: int = 90) -> None:
        """Initialize TTL pruning strategy.

        Args:
            max_age_days: Maximum age in days (default 90).
        """
        self.max_age_days = max_age_days

    @property
    def name(self) -> str:
        """Human-readable strategy name."""
        return "ttl"

    async def prune(
        self,
        *,
        agent_id: NotBlankStr,  # noqa: ARG002
        entries: tuple[MemoryEntry, ...],
    ) -> tuple[str, ...]:
        """Identify entries exceeding max age for removal.

        Args:
            agent_id: Agent whose memories are being pruned.
            entries: Current procedural memory entries.

        Returns:
            Tuple of memory entry IDs to remove.
        """
        now = datetime.now(UTC)
        to_remove = []

        for entry in entries:
            age_days = (now - entry.created_at).days
            if age_days > self.max_age_days:
                to_remove.append(str(entry.id))

        return tuple(to_remove)
