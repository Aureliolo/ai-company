"""Retention manager -- prune old backups by count and age."""

import json
import shutil
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from synthorg.backup.errors import RetentionError
from synthorg.backup.models import BackupManifest, BackupTrigger
from synthorg.observability import get_logger
from synthorg.observability.events.backup import (
    BACKUP_MANIFEST_INVALID,
    BACKUP_RETENTION_FAILED,
    BACKUP_RETENTION_PRUNED,
)

if TYPE_CHECKING:
    from pathlib import Path

    from synthorg.backup.config import RetentionConfig

logger = get_logger(__name__)


class RetentionManager:
    """Prune old backups based on count and age policies.

    Never prunes the most recent backup or backups tagged
    with ``pre_migration`` trigger.

    Args:
        config: Retention policy configuration.
        backup_path: Root directory containing all backups.
    """

    def __init__(self, config: RetentionConfig, backup_path: Path) -> None:
        self._config = config
        self._backup_path = backup_path

    async def prune(self) -> tuple[str, ...]:
        """Remove backups that exceed count or age limits.

        Returns:
            Tuple of pruned backup IDs.

        Raises:
            RetentionError: If pruning fails.
        """
        try:
            manifests = self._load_manifests()
        except Exception as exc:
            logger.error(
                BACKUP_RETENTION_FAILED,
                error=str(exc),
                exc_info=True,
            )
            msg = f"Failed to load manifests: {exc}"
            raise RetentionError(msg) from exc

        if not manifests:
            return ()

        # Sort by timestamp descending (newest first)
        manifests.sort(key=lambda m: m.timestamp, reverse=True)
        candidates = self._identify_prunable(manifests)
        return self._execute_prune(candidates)

    def _identify_prunable(
        self,
        manifests: list[BackupManifest],
    ) -> list[BackupManifest]:
        """Identify manifests eligible for pruning."""
        now = datetime.now(UTC)
        max_age = timedelta(days=self._config.max_age_days)
        candidates: list[BackupManifest] = []

        for i, manifest in enumerate(manifests):
            if i == 0:
                continue
            if manifest.trigger == BackupTrigger.PRE_MIGRATION:
                continue
            if self._should_prune(i, manifest, now, max_age):
                candidates.append(manifest)

        return candidates

    def _should_prune(
        self,
        index: int,
        manifest: BackupManifest,
        now: datetime,
        max_age: timedelta,
    ) -> bool:
        """Determine if a single manifest should be pruned."""
        if index >= self._config.max_count:
            return True
        try:
            backup_time = datetime.fromisoformat(manifest.timestamp)
            if now - backup_time > max_age:
                return True
        except ValueError:
            pass
        return False

    def _execute_prune(
        self,
        candidates: list[BackupManifest],
    ) -> tuple[str, ...]:
        """Delete candidate backups and return pruned IDs."""
        pruned: list[str] = []
        for manifest in candidates:
            try:
                self._delete_backup(manifest.backup_id)
                pruned.append(manifest.backup_id)
                logger.info(
                    BACKUP_RETENTION_PRUNED,
                    backup_id=manifest.backup_id,
                    trigger=manifest.trigger.value,
                    timestamp=manifest.timestamp,
                )
            except Exception as exc:
                logger.error(
                    BACKUP_RETENTION_FAILED,
                    backup_id=manifest.backup_id,
                    error=str(exc),
                    exc_info=True,
                )
        return tuple(pruned)

    def _load_manifests(self) -> list[BackupManifest]:
        """Load all manifest.json files from the backup directory."""
        manifests: list[BackupManifest] = []
        if not self._backup_path.exists():
            return manifests

        for entry in self._backup_path.iterdir():
            manifest_path = None
            if entry.is_dir():
                manifest_path = entry / "manifest.json"
            elif entry.suffix == ".gz" and entry.stem.endswith(".tar"):
                # Compressed backups -- manifest is inside the archive
                # Skip for now; manifests from compressed backups are
                # loaded during list_backups via tar extraction
                continue

            if manifest_path is not None and manifest_path.exists():
                try:
                    data = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifests.append(BackupManifest.model_validate(data))
                except Exception:
                    logger.debug(
                        BACKUP_MANIFEST_INVALID,
                        path=str(manifest_path),
                    )

        return manifests

    def _delete_backup(self, backup_id: str) -> None:
        """Delete a backup directory or archive by ID."""
        for entry in self._backup_path.iterdir():
            if entry.is_dir() and entry.name.startswith(backup_id):
                shutil.rmtree(str(entry))
                return
            if entry.is_file() and entry.name.startswith(backup_id):
                entry.unlink()
                return

        # Also check if backup_id matches the manifest inside directories
        for entry in self._backup_path.iterdir():
            if not entry.is_dir():
                continue
            manifest_path = entry / "manifest.json"
            if not manifest_path.exists():
                continue
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                if data.get("backup_id") == backup_id:
                    shutil.rmtree(str(entry))
                    return
            except Exception:
                logger.debug(
                    BACKUP_MANIFEST_INVALID,
                    path=str(manifest_path),
                )
