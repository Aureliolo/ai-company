"""Component handler protocol for backup/restore operations.

Defines the structural interface that each backup component
handler must satisfy.
"""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pathlib import Path

    from synthorg.backup.models import BackupComponent


@runtime_checkable
class ComponentHandler(Protocol):
    """Structural interface for per-component backup/restore.

    Each handler knows how to back up and restore a single
    data component (persistence DB, agent memory, or config).
    """

    @property
    def component(self) -> BackupComponent:
        """Return the component this handler manages."""
        ...

    async def backup(self, target_dir: Path) -> int:
        """Back up the component data to *target_dir*.

        Args:
            target_dir: Directory to write backup files into.

        Returns:
            Total bytes written.
        """
        ...

    async def restore(self, source_dir: Path) -> None:
        """Restore the component data from *source_dir*.

        Args:
            source_dir: Directory containing backup files.
        """
        ...

    async def validate_source(self, source_dir: Path) -> bool:
        """Validate that *source_dir* contains a restorable backup.

        Args:
            source_dir: Directory to validate.

        Returns:
            ``True`` if the backup data is valid.
        """
        ...
