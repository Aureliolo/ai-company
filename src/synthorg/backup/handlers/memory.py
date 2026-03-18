"""Memory component handler -- copytree-based backup of agent memory."""

import asyncio
import shutil
from pathlib import Path

from synthorg.backup.errors import ComponentBackupError
from synthorg.backup.models import BackupComponent
from synthorg.observability import get_logger
from synthorg.observability.events.backup import (
    BACKUP_COMPONENT_COMPLETED,
    BACKUP_COMPONENT_FAILED,
    BACKUP_COMPONENT_STARTED,
)

logger = get_logger(__name__)

_MEMORY_SUBDIR = "memory"


class MemoryComponentHandler:
    """Back up and restore the agent memory data directory.

    Uses ``shutil.copytree`` for directory-level copies of the
    Mem0 data directory (Qdrant + history DB).

    Args:
        data_dir: Path to the memory data directory.
    """

    def __init__(self, data_dir: str) -> None:
        self._data_dir = data_dir

    @property
    def component(self) -> BackupComponent:
        """Return the component this handler manages."""
        return BackupComponent.MEMORY

    async def backup(self, target_dir: Path) -> int:
        """Copy the memory data directory to the backup target.

        Args:
            target_dir: Directory to write the backup into.

        Returns:
            Total bytes written.

        Raises:
            ComponentBackupError: If the backup operation fails.
        """
        logger.info(
            BACKUP_COMPONENT_STARTED,
            component=self.component.value,
            data_dir=self._data_dir,
        )
        source = Path(self._data_dir)
        exists = await asyncio.to_thread(source.exists)
        if not exists:
            logger.info(
                BACKUP_COMPONENT_COMPLETED,
                component=self.component.value,
                size_bytes=0,
                note="source directory does not exist, skipping",
            )
            return 0

        target = target_dir / _MEMORY_SUBDIR
        try:
            size = await asyncio.to_thread(self._copy_tree, source, target)
        except Exception as exc:
            logger.error(
                BACKUP_COMPONENT_FAILED,
                component=self.component.value,
                error=str(exc),
                exc_info=True,
            )
            msg = f"Failed to back up memory data: {exc}"
            raise ComponentBackupError(msg) from exc
        logger.info(
            BACKUP_COMPONENT_COMPLETED,
            component=self.component.value,
            size_bytes=size,
        )
        return size

    async def restore(self, source_dir: Path) -> None:
        """Restore memory data from a backup.

        Performs an atomic swap: renames current directory to
        ``.bak``, copies backup into place.  On failure, renames
        ``.bak`` back.

        Args:
            source_dir: Directory containing the backup memory data.

        Raises:
            ComponentBackupError: If restore fails.
        """
        source = source_dir / _MEMORY_SUBDIR
        if not source.exists():
            msg = f"Backup memory directory not found: {source}"
            raise ComponentBackupError(msg)

        data_path = Path(self._data_dir)
        bak_path = data_path.with_name(f"{data_path.name}.bak")

        try:
            await asyncio.to_thread(
                self._atomic_swap,
                data_path,
                source,
                bak_path,
            )
        except ComponentBackupError:
            raise
        except Exception as exc:
            msg = f"Failed to restore memory data: {exc}"
            raise ComponentBackupError(msg) from exc

    async def validate_source(self, source_dir: Path) -> bool:
        """Validate that the backup memory directory exists.

        Args:
            source_dir: Directory to validate.

        Returns:
            ``True`` if the memory backup subdirectory exists.
        """
        return (source_dir / _MEMORY_SUBDIR).exists()

    @staticmethod
    def _copy_tree(source: Path, target: Path) -> int:
        """Copy directory tree and return total bytes copied."""
        shutil.copytree(str(source), str(target))
        total = 0
        for f in target.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
        return total

    @staticmethod
    def _atomic_swap(
        data_path: Path,
        source: Path,
        bak_path: Path,
    ) -> None:
        """Swap the live directory with the backup, rolling back on failure."""
        if data_path.exists():
            shutil.move(str(data_path), str(bak_path))

        try:
            shutil.copytree(str(source), str(data_path))
        except Exception:
            if bak_path.exists():
                if data_path.exists():
                    shutil.rmtree(str(data_path))
                shutil.move(str(bak_path), str(data_path))
            raise

        if bak_path.exists():
            shutil.rmtree(str(bak_path))
