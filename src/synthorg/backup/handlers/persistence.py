"""Persistence component handler -- SQLite VACUUM INTO backup."""

import asyncio
import shutil
import sqlite3
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

_DB_FILENAME = "synthorg.db"


class PersistenceComponentHandler:
    """Back up and restore the SQLite persistence database.

    Uses ``VACUUM INTO`` for consistent, point-in-time copies
    without WAL/SHM complications.

    Args:
        db_path: Path to the live SQLite database file.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    @property
    def component(self) -> BackupComponent:
        """Return the component this handler manages."""
        return BackupComponent.PERSISTENCE

    async def backup(self, target_dir: Path) -> int:
        """Create a VACUUM INTO copy of the database.

        Args:
            target_dir: Directory to write the backup database into.

        Returns:
            Size of the backup file in bytes.

        Raises:
            ComponentBackupError: If the backup operation fails.
        """
        logger.info(
            BACKUP_COMPONENT_STARTED,
            component=self.component.value,
            db_path=self._db_path,
        )
        target_file = target_dir / _DB_FILENAME
        try:
            size = await asyncio.to_thread(
                self._vacuum_into,
                self._db_path,
                str(target_file),
            )
        except Exception as exc:
            logger.error(
                BACKUP_COMPONENT_FAILED,
                component=self.component.value,
                error=str(exc),
                exc_info=True,
            )
            msg = f"Failed to back up persistence DB: {exc}"
            raise ComponentBackupError(msg) from exc
        logger.info(
            BACKUP_COMPONENT_COMPLETED,
            component=self.component.value,
            size_bytes=size,
        )
        return size

    async def restore(self, source_dir: Path) -> None:
        """Restore the database from a backup copy.

        Performs an atomic swap: renames current DB to ``.bak``,
        copies backup into place, validates.  On failure, renames
        ``.bak`` back.

        Args:
            source_dir: Directory containing the backup database.

        Raises:
            ComponentBackupError: If restore fails.
        """
        source_file = source_dir / _DB_FILENAME
        if not source_file.exists():
            msg = f"Backup database not found: {source_file}"
            raise ComponentBackupError(msg)

        db_path = Path(self._db_path)
        bak_path = db_path.with_suffix(".db.bak")

        try:
            await asyncio.to_thread(self._atomic_swap, db_path, source_file, bak_path)
        except ComponentBackupError:
            raise
        except Exception as exc:
            msg = f"Failed to restore persistence DB: {exc}"
            raise ComponentBackupError(msg) from exc

    async def validate_source(self, source_dir: Path) -> bool:
        """Validate that the backup database passes integrity check.

        Args:
            source_dir: Directory containing the backup database.

        Returns:
            ``True`` if the database is valid.
        """
        source_file = source_dir / _DB_FILENAME
        if not source_file.exists():
            return False
        try:
            return await asyncio.to_thread(
                self._check_integrity,
                str(source_file),
            )
        except Exception:
            return False

    @staticmethod
    def _vacuum_into(source_path: str, target_path: str) -> int:
        """Execute VACUUM INTO to produce a consistent copy.

        Args:
            source_path: Path to the live database.
            target_path: Path for the backup copy.

        Returns:
            Size of the resulting backup file in bytes.
        """
        conn = sqlite3.connect(source_path)
        try:
            conn.execute("VACUUM INTO ?", (target_path,))
        finally:
            conn.close()
        return Path(target_path).stat().st_size

    @staticmethod
    def _check_integrity(db_path: str) -> bool:
        """Run PRAGMA integrity_check on a database file."""
        conn = sqlite3.connect(db_path)
        try:
            result = conn.execute("PRAGMA integrity_check").fetchone()
            return result is not None and result[0] == "ok"
        finally:
            conn.close()

    @staticmethod
    def _atomic_swap(
        db_path: Path,
        source_file: Path,
        bak_path: Path,
    ) -> None:
        """Swap the live DB with the backup, rolling back on failure."""
        # Move current to .bak
        if db_path.exists():
            shutil.move(str(db_path), str(bak_path))

        try:
            shutil.copy2(str(source_file), str(db_path))
            # Validate the restored copy
            conn = sqlite3.connect(str(db_path))
            try:
                result = conn.execute("PRAGMA integrity_check").fetchone()
                if result is None or result[0] != "ok":
                    msg = "Restored database failed integrity check"
                    raise ComponentBackupError(msg)
            finally:
                conn.close()
        except Exception:
            # Rollback: restore the original
            if bak_path.exists():
                if db_path.exists():
                    db_path.unlink()
                shutil.move(str(bak_path), str(db_path))
            raise

        # Cleanup .bak on success
        if bak_path.exists():
            bak_path.unlink()
